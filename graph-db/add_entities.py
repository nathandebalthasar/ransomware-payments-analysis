import requests
import os

from shared import get_driver

IKNA_ENDPOINT = str(os.getenv("IKNA_ENDPOINT"))
IKNA_TOKEN = str(os.getenv("IKNA_TOKEN"))

if not IKNA_ENDPOINT or not IKNA_TOKEN:
    raise ValueError("IKNA_ENDPOINT and IKNA_TOKEN must be set in the environment variables.")

BATCH_SIZE = 5000

driver = get_driver()

# Get addresses from neo4j
def get_all_addresses():
    with driver.session() as session:
        result = session.run("MATCH (a:Address) RETURN a.address AS address")
        return [record["address"] for record in result]

# Get entity for all addresses
def fetch_entities_for_addresses(addresses):
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
        raise RuntimeError(f"HTTP error occurred: {http_err}") from http_err

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

# Update addresses tag in neo4j with entity info
def update_address_tag(session, address, tag_label, category):
    res = session.run(
        """
        MATCH (a:Address {address: $address})
        SET a.tag = $tag, a.category = $category
        """,
        {"address": address, "tag": tag_label, "category": category}
    )
    if res.consume().counters.properties_set > 0:
        print(f"Updated {address} with tag '{tag_label}' in category '{category}'")
    else:
        print(f"No update for {address} (already tagged?)")

def main():
    all_addresses = get_all_addresses()
    print(f"Loaded {len(all_addresses)} addresses from Neo4j.")

    with driver.session() as session:
        for i in range(0, len(all_addresses), BATCH_SIZE):
            batch = all_addresses[i:i+BATCH_SIZE]
            print(f"Processing batch {i//BATCH_SIZE + 1}/{(len(all_addresses)-1)//BATCH_SIZE + 1}...")

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
                    print(f"Tagging {address} as '{label}' ({category})")
                    update_address_tag(session, address, label, category)


    driver.close()
    print("Done tagging addresses with labels.")

if __name__ == "__main__":
    main()
