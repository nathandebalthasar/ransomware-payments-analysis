"""
Script used to create the transaction graph using ElectrumX and Neo4j
Usage: python3 initialize.py <seed_file> <depth>
"""


import sys
import time
import json
import socket
import hashlib
import base58
import os
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from functools import partial
from bech32 import bech32_decode, convertbits
from shared import get_driver
import query
from logger import log

HOST = os.getenv("ELECTRUMX_HOST", "localhost")
PORT = int(os.getenv("ELECTRUMX_PORT", 50001))

executor = ThreadPoolExecutor(max_workers=50)
visited_lock = threading.Lock()
submitted_futures = []
submitted_futures_lock = threading.Lock()

def address_to_scripthash(addr):
    """
    Function to extract the scripthash from a BTC address.
    """
    if addr.startswith(('1','3')):
        payload = base58.b58decode_check(addr)
        if addr.startswith('1'):
            script = b'\x76\xa9\x14' + payload[1:] + b'\x88\xac'
        else:
            script = b'\xa9\x14' + payload[1:] + b'\x87'
    elif addr.startswith('bc1'):
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
    return hashlib.sha256(script).digest()[::-1].hex()

def electrum_request(method, params, max_retries=3):
    """
    Perform a TCP request to ElectrumX.
    """
    request_json = json.dumps({"id": 1, "method": method, "params": params}) + "\n"
    for _ in range(max_retries):
        try:
            with socket.create_connection((HOST, PORT), timeout=30) as sock:
                sock.sendall(request_json.encode())
                buffer = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    if b"\n" in chunk:
                        break
            response = buffer.decode(errors="ignore").strip()
            if not response or len(response) < 10:
                continue
            try:
                resp_json = json.loads(response)
            except json.JSONDecodeError:
                continue
            if "error" in resp_json:
                raise RuntimeError(f"ElectrumX error: {resp_json['error']}")
            return resp_json.get("result")
        except (socket.timeout, socket.error):
            time.sleep(1)
    log.info(f"Failed to fetch {method} {params}")
    return None

def sum_of_outputs(vout):
    """
    Retrieve the total value traded per address given all outputs of an address.
    """
    return sum(o.get("value", 0) / 100_000_000 for o in vout)

def fetch_address_data(address):
    """
    Retrieve the tx_ids of all transactions for a given address.
    """
    scripthash = address_to_scripthash(address)
    history = electrum_request("blockchain.scripthash.get_history", [scripthash])
    all_txs = []
    for entry in history:
        txid = entry["tx_hash"]
        tx = electrum_request("blockchain.transaction.get", [txid, True])
        tx["block_height"] = entry.get("height")
        all_txs.append(tx)
    return {"address": address, "txs": all_txs}

def safe_check_and_add(address, depth, visited):
    """
    Verify whether or not an address has already been visited.
    """
    with visited_lock:
        existing = visited.get(address)
        if existing is not None and existing >= depth:
            return False
        visited[address] = depth
        return True

def submit_crawl(driver, address, depth, visited, isSeed=False):
    """
    Submit a new crawl_address job.
    """
    future = executor.submit(partial(crawl_address, driver, address, depth, visited, isSeed))
    with submitted_futures_lock:
        submitted_futures.append(future)

def crawl_address(driver, address, depth, visited, isSeed=False):
    """
    Wrapper that checks if a node has been visited and executes the crawl function.
    """
    log.info(f"[ENTRY] crawl_address called for {address} at depth {depth}")
    if depth <= 0 or not safe_check_and_add(address, depth, visited):
        log.info(f"Skipping {address} (depth {depth})")
        return
    with driver.session() as session:
        _crawl(session, driver, address, depth, visited, isSeed)

def _crawl(session, driver, address, depth, visited, isSeed=False):
    """
    Internal crawl method, main function of the program to add new nodes.
    """
    log.info(f"Crawling {address} (depth {depth})")
    try:
        data = fetch_address_data(address)
    except Exception as e:
        log.info(f"\tFailed to fetch {address}: {e}")
        return

    session.execute_write(query.create_address_node, address)
    # if isSeed:
    #     session.execute_write(query.label_seed_address, address)

    if len(data["txs"]) > 100:
        session.execute_write(query.label_service_address, address)
        log.info(f"\tSkipping {address}: too many transactions ({len(data['txs'])})")
        return

    for tx in data["txs"]:
        txid = tx["txid"]
        timestamp = tx.get("time", 0)
        block_height = tx.get("block_height")
        fee = tx.get("fee", 0)
        vin = tx.get("vin", [])
        vout = tx.get("vout", [])

        if sum_of_outputs(vout) > 5:
            log.info(f"\tSkipping {address} TX {txid}: output sum too high")
            session.execute_write(query.label_service_address, address)
            continue

        if len(vin) > 20 or len(vout) > 20:
            log.info(f"\tSkipping {address} TX {txid}: too many inputs/outputs")
            session.execute_write(query.label_service_address, address)
            continue

        session.execute_write(query.create_transaction_node, txid, timestamp, block_height, fee)
        log.info(f"\t{address} TX {txid}: {len(vin)} inputs, {len(vout)} outputs")

        for i in vin:
            prev_txid = i.get("txid")
            vout_index = i.get("vout")
            if not prev_txid or vout_index is None:
                log.info(f"\tSkipping {address} TX {txid}: invalid input {i}")
                continue
            try:
                prev_tx = electrum_request("blockchain.transaction.get", [prev_txid, True])
                prev_vout = prev_tx["vout"][vout_index]
                script = prev_vout.get("scriptPubKey", {})
                input_addr = script.get("addresses", [None])[0]
            except Exception as e:
                log.info(f"\tFailed to fetch prev tx {prev_txid}: {e}")
                input_addr = None
            if input_addr:
                session.execute_write(query.create_address_node, input_addr)
                session.execute_write(query.create_input_link, input_addr, txid)
                submit_crawl(driver, input_addr, depth - 1, visited)

        for o in vout:
            script = o.get("scriptPubKey", {})
            output_addr = script.get("addresses", [None])[0]
            value = o.get("value", 0) / 100_000_000
            if output_addr:
                session.execute_write(query.create_address_node, output_addr)
                session.execute_write(query.create_output_link, output_addr, txid, value)
                submit_crawl(driver, output_addr, depth - 1, visited)

    time.sleep(0.05)

def main(file_path, depth):
    """
    Entry point of the program.
    """
    driver = get_driver()
    visited = {}

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            seed = line.strip()
            if seed:
                submit_crawl(driver, seed, depth, visited, True)

    # Wait for all submitted recursive jobs
    while True:
        with submitted_futures_lock:
            current_futures = list(submitted_futures)
        _, not_done = wait(current_futures, timeout=10, return_when="ALL_COMPLETED")
        if not not_done:
            log.info("All futures completed.")
            break
        log.info(f"{len(not_done)} futures still pending...")

    executor.shutdown()
    driver.close()
    log.info("Done crawling and importing.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        log.info("Usage: python crawl_addresses_with_depth.py <file_path> <depth>")
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        depth = int(sys.argv[2])
    except ValueError:
        log.info("Error: depth must be an integer.")
        sys.exit(1)

    main(file_path, depth)
