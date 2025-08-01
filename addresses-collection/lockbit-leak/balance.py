"""
Retrieve the balance of Bitcoin addresses collected from the Lockbit data breach.
"""

import requests
import os

def load_addresses(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")

    with open(file_path, "r") as f:
        addresses = [line.strip() for line in f if line.strip()]
    return addresses

def get_balance(address):
    url = f"https://blockstream.info/api/address/{address}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        confirmed = data["chain_stats"]["funded_txo_sum"] - data["chain_stats"]["spent_txo_sum"]
        mempool = data["mempool_stats"]["funded_txo_sum"] - data["mempool_stats"]["spent_txo_sum"]
        return (confirmed + mempool) / 1e8  # Satoshi to BTC conversion
    else:
        return None

addresses = load_addresses("active_addresses.txt")

for addr in addresses:
    balance = get_balance(addr)
    print(f"{addr}: {balance} BTC")
