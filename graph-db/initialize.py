import sys
import time
import json
import socket
import hashlib
import base58
from bech32 import bech32_decode, convertbits
from shared import get_driver
import query
import os

HOST = os.getenv("ELECTRUMX_HOST", "localhost")
PORT = int(os.getenv("ELECTRUMX_PORT", 50001))

# Convert Bitcoin address to ElectrumX scripthash
def address_to_scripthash(addr):
    if addr.startswith(('1','3')): # Legacy addresses (P2PKH or P2SH)
        payload = base58.b58decode_check(addr)
        if addr.startswith('1'):
            script = b'\x76\xa9\x14' + payload[1:] + b'\x88\xac'
        else:
            script = b'\xa9\x14' + payload[1:] + b'\x87'
    elif addr.startswith('bc1'): # Bech32 SegWit addresses
        _, data = bech32_decode(addr)
        decoded = convertbits(data[1:], 5, 8, False)
        witver = data[0]
        if witver == 0 and len(decoded) == 20:
            script = b'\x00\x14' + bytes(decoded)
        elif witver == 0 and len(decoded) == 32:
            script = b'\x00\x20' + bytes(decoded)
        elif witver == 1 and len(decoded) == 32:
            script = b'\x51\x20' + bytes(decoded)
        else:
            raise ValueError("Unsupported address")
    else:
        raise ValueError("Unsupported address type")
    return hashlib.sha256(script).digest()[::-1].hex() # Reverse for ElectrumX scripthash

# Electrum request with retry logic
def electrum_request(method, params, max_retries=3):
    # Construct the request
    request_json = json.dumps({"id": 1, "method": method, "params": params}) + "\n"

    # Retry logic if the request fails
    for attempt in range(max_retries):
        try:
            with socket.create_connection((HOST, PORT), timeout=30) as sock:
                sock.sendall(request_json.encode())

                buffer = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk: # If no data is received, close the connection
                        break
                    buffer += chunk
                    if b"\n" in chunk: # JSON-RPC responses end with a newline
                        break

            response = buffer.decode(errors="ignore").strip()

            if not response or len(response) < 10:
                print(f"Empty or short response, retrying (attempt {attempt+1}/{max_retries})...")
                continue

            try:
                resp_json = json.loads(response)
            except json.JSONDecodeError as e:
                print(f"Failed to parse response JSON: {e}")
                continue

            if "error" in resp_json:
                raise RuntimeError(f"ElectrumX error: {resp_json['error']}")

            return resp_json.get("result")

        except (socket.timeout, socket.error) as e:
            print(f"Socket error on attempt {attempt+1}/{max_retries}: {e}")
            time.sleep(1)

    # After retries, give up
    print(f"Failed to fetch {method} {params} after {max_retries} retries.")
    return None

def sum_of_outputs(vout):
    """Calculate the sum of output values in a transaction."""
    return sum(o.get("value", 0) / 100_000_000 for o in vout)

#  Fetch all transactions (inputs/outputs) for an address using ElectrumX
def fetch_address_data(address):
    scripthash = address_to_scripthash(address)
    history = electrum_request("blockchain.scripthash.get_history", [scripthash])

    all_txs = []
    for entry in history:
        txid = entry["tx_hash"]
        tx = electrum_request("blockchain.transaction.get", [txid, True])
        tx["block_height"] = entry.get("height")
        all_txs.append(tx)

    return {"address": address, "txs": all_txs}

# Recursive crawl addresses
def crawl_address(session, address, depth, visited, isSeed=False):
    if depth <= 0 or address in visited:
        return

    visited.add(address)
    print(f"Crawling {address} (depth {depth})")

    try:
        data = fetch_address_data(address)
    except Exception as e:
        print(f"\tCould not fetch {address}: {e}")

        # If the address could not be fetched, create an Unknown Address node
        # session.execute_write(query.create_address_node, address)
        # session.execute_write(query.tag_unknown_address, address)

        return

    # Create the Address node
    session.execute_write(query.create_address_node, address)

    if isSeed:
        session.execute_write(query.label_seed_address, address)

    if (len(data["txs"]) > 100):
        print(f"\tToo many txs for {address}, skipping further crawling.")
        session.execute_write(query.label_service_address, address)
        return

    for tx in data["txs"]:
        txid = tx["txid"]
        timestamp = tx.get("time", 0)
        block_height = tx.get("block_height")
        fee = tx.get("fee", 0)

        session.execute_write(query.create_transaction_node, txid, timestamp, block_height, fee)

        # Transactions (inputs/outputs)
        vin = tx.get("vin", [])
        vout = tx.get("vout", [])

        if (sum_of_outputs(vout) > 5):
            print(f"\tSkipping {txid} (output sum > 5 BTC)")
            session.execute_write(query.label_service_address, address)
            continue

        print(f"\t{address} TX {txid}: {len(vin)} inputs, {len(vout)} outputs")

        # Skip if more than 20 inputs or outputs
        if len(vin) > 20 or len(vout) > 20:
            print(f"\tSkipping {txid} (too many inputs/outputs)")
            session.execute_write(query.label_service_address, address)
            continue

        for i in vin:
            prev_txid = i.get("txid")
            vout_index = i.get("vout")

            if not prev_txid or vout_index is None:
                continue # Skip if no previous transaction or vout index

            # Fetch the previous transaction to get the input address
            try:
                prev_tx = electrum_request("blockchain.transaction.get", [prev_txid, True])
                prev_vout = prev_tx["vout"][vout_index]
                script = prev_vout.get("scriptPubKey", {})
                input_addr = None
                if "addresses" in script:
                    input_addr = script["addresses"][0]
                elif "addr" in prev_vout:
                    input_addr = prev_vout["addr"]
            except Exception as e:
                print(f"\tCould not fetch prev tx {prev_txid}: {e}")

                if "history too large" in str(e):
                    print(f"\tSkipping {prev_txid} due to history size limit.")
                    session.execute_write(query.label_service_address, address)
                    continue

                input_addr = None

            if not input_addr:
                continue

            session.execute_write(query.create_address_node, input_addr)
            session.execute_write(query.create_input_link, input_addr, txid)
            crawl_address(session, input_addr, depth - 1, visited)

        for o in vout:
            output_addr = None
            script = o.get("scriptPubKey", {}) # Get the scriptPubKey
            if "addresses" in script:
                output_addr = script["addresses"][0]
            elif "addr" in o:
                output_addr = o["addr"]
            value = o.get("value", 0) / 100_000_000 # Convert satoshis to BTC
            if not output_addr:
                continue
            session.execute_write(query.create_address_node, output_addr)
            session.execute_write(query.create_output_link, output_addr, txid, value)
            crawl_address(session, output_addr, depth - 1, visited)

    # Avoid overloading the server with requests
    time.sleep(0.2)


# Main function
def main(file_path, depth):
    driver = get_driver()
    visited = set()

    with driver.session() as session:
        with open(file_path, 'r', encoding='utf-8') as f: # Open and read seed address file
            for line in f:
                seed = line.strip()
                if seed:
                    session.execute_write(query.label_seed_address, seed)
                    crawl_address(session, seed, depth, visited, True)

    driver.close()
    print("Done crawling and importing.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python crawl_addresses_with_depth.py <file_path> <depth>")
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        depth = int(sys.argv[2])
    except ValueError:
        print("Error: depth must be an integer.")
        sys.exit(1)

    main(file_path, depth)
