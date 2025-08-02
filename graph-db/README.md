# Graph-db

This directory contains scripts to initialize the neo4j database with addresses starting from seed addresses, and add identified entities to it.

## Usage

1. Fill in the `.env` file based on the `.env.template` one. Run the initialization script with an initial seed addresses file and given depth.
```bash
pipenv run python initialize.py seed_addresses.txt 2
```

2. After the database is initialized, run the `add_entities.py` script to fetch and add entity information for all addresses in the database.
```bash
pipenv run python add_entities.py
```
