"""
Script to attribute entities using GraphSense to all nodes within the neo4j graph.
"""

import requests
import shared
import os
from logger import log

driver = shared.get_driver()

BATCH_SIZE = 5000

IKNA_ENDPOINT = os.getenv("IKNA_ENDPOINT")
IKNA_TOKEN = os.getenv("IKNA_TOKEN")

if not IKNA_ENDPOINT or not IKNA_TOKEN:
    raise ValueError("IKNA_ENDPOINT and IKNA_TOKEN must be defined.")

def get_all_addresses():
    """
    Retrieve all addresses from the transaction graph.
    """
    with driver.session() as session:
        result = session.run("MATCH (a:Address) RETURN a.address AS address")
        return [record["address"] for record in result]

def fetch_entities_for_addresses(addresses):
    """
    Uses GraphSense to retrieve entities for all addresses.
    """
    payload = {"address": addresses}
    headers = {
        "Authorization": f"{IKNA_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(IKNA_ENDPOINT, headers=headers, json=payload, timeout=3600)
        response.raise_for_status()
        return response.json()

    except requests.HTTPError as http_err:
        log.error(f"HTTPError while fetching GraphSense: {http_err}")
        raise

    except requests.RequestException as e:
        log.error(f"RequestException while fetching GraphSense: {e}")
        return None


def update_address_tag(session, address, tag_label, category):
    """
    Update tags within the transaction graph using the entities retrieved
    using GraphSense.
    """
    res = session.run(
        """
        MATCH (a:Address {address: $address})
        SET a.tag = $tag, a.category = $category
        """,
        {"address": address, "tag": tag_label, "category": category}
    )
    if res.consume().counters.properties_set > 0:
        log.info(f"Updated {address} with tag {tag_label} in category {category}")
    else:
        log.info(f"No update for {address} (already tagged?)")

def main():
    """"
    Main function of the program that orchestrates tagging.
    """
    all_addresses = get_all_addresses()
    log.info(f"Loaded {len(all_addresses)} addresses from Neo4j.")

    with driver.session() as session:
        for i in range(0, len(all_addresses), BATCH_SIZE):
            batch = all_addresses[i:i+BATCH_SIZE]
            log.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(all_addresses)-1)//BATCH_SIZE + 1}...")

            data = fetch_entities_for_addresses(batch)
            if not data:
                continue

            results = data if isinstance(data, list) else data.get("data", [])
            for entry in results:
                address = entry.get("_request_address")
                tag_info = entry.get("best_address_tag", {})
                label = tag_info.get("label")
                category = tag_info.get("category")
                if address and label:
                    log.info(f"Tagging {address} as '{label}' ({category})")
                    update_address_tag(session, address, label, category)


    driver.close()
    log.info("Done tagging.")

if __name__ == "__main__":
    main()
