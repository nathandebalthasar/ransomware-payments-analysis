# Graph-db

This directory contains scripts to initialize the neo4j database with addresses starting from seed addresses, and add identified entities to it.

## Pre-requisites

- [ElectrumX server](link)
- [GraphSense API key](link)
- [Neo4j](link)

## Usage

1. Fill in the `.env` file based on the `.env.template` one. Run the initialization script with an initial seed addresses file and given depth. This script will retrieve all transactions for the addresses in the file passed as parameter with the given depth, and store them in a neo4j database.
```bash
pipenv run python initialize.py seed_addresses.txt 2
```

2. After the database is initialized, run the `add_entities.py` script to fetch and add entity information for all addresses in the database. This script will fetch entity information from the GraphSense API and add it to the nodes being tagged.
```bash
pipenv run python add_entities.py
```

You may apply rule-based filtering in neo4j Bloom to display Seed, Unknown, Service, and other entities with colors. [Documentation](https://neo4j.com/docs/bloom-user-guide/current/bloom-visual-tour/legend-panel/)
