# Ransomware payments analysis

This repository contains several scripts and resources used to write my MSc thesis on the topic of ransomware payments. Its goal was to provide an open-source framework for analyzing ransomware payment data, as an alternative to the proprietary solutions available (e.g., Chainalysis, Elliptic, etc.).

## Structure

- `addresses-collection/`: Contains a list of scripts that were used to collect Bitcoin addresses suspected from belonging to ransomware operations (victims, affiliates, operators or other actors).
- `graph-db/`: Contains scripts to initialize a Neo4j graph database with the collected addresses and add entity information to it.
