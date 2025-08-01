"""
Script used to collect Bitcoin addresses from the Lockbit data breach.
Only save addresses that have at least one transaction.
"""

import mysql.connector
import requests
import time
from tqdm import tqdm

# DB config
db_config = {
    'host': '<host>',
    'user': '<user>',
    'password': '<password>',
    'database': 'paneldb_dump'
}

OUTPUT_PATH = "active_addresses.txt"

# Connect to the database and load addresses
def load_addresses():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT address FROM btc_addresses")
    results = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results

# Check if address has transactions
def has_transactions(address):
    url = f'https://blockstream.info/api/address/{address}'
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data['chain_stats']['tx_count'] > 0
    except:
        return False
    return False

def main():
    addresses = load_addresses()
    active_addresses = []

    for addr in tqdm(addresses):
        if has_transactions(addr):
            active_addresses.append(addr)
            print(f"Active address found: {addr}")
        time.sleep(0.1)  # Avoid spamming the API

    with open(OUTPUT_PATH, "w") as f:
        for a in active_addresses:
            f.write(a + "\n")

if __name__ == "__main__":
    main()
