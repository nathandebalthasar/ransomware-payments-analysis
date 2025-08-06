"""
Contains all neo4j queries to initialize the database as well as
their wrapper function.
"""


CREATE_ADDRESS_QUERY = """
MERGE (a:Address {address: $address})
"""

CREATE_TX_QUERY = """
MERGE (t:Transaction {txid: $txid})
SET t.timestamp = $timestamp,
    t.block_height = $block_height,
    t.fee = $fee
"""

CREATE_INPUT_REL = """
MATCH (a:Address {address: $address})
MATCH (t:Transaction {txid: $txid})
MERGE (a)-[:INPUT_OF]->(t)
"""

CREATE_OUTPUT_REL = """
MATCH (a:Address {address: $address})
MATCH (t:Transaction {txid: $txid})
MERGE (t)-[:OUTPUT_OF {amount: $amount}]->(a)
"""

LABEL_SEED_ADDRESS_QUERY = """
MATCH (a:Address {address: $address})
SET a:Seed
"""

TAG_UNKNOWN_ADDRESS_QUERY = """
MATCH (a:Address {address: $address})
SET a:Unknown
"""

LABEL_SERVICE_ADDRESS_QUERY = """
MATCH (a:Address {address: $address})
SET a:Service
"""

CREATE_UNKNOWN_TX_QUERY = """
MERGE (t:Transaction:UnknownTx {txid: $txid})
"""

def create_input_link(tx, address, txid):
    tx.run(CREATE_INPUT_REL, {"address": address, "txid": txid})

def tag_unknown_address(tx, address):
    tx.run(TAG_UNKNOWN_ADDRESS_QUERY, {"address": address})

def create_output_link(tx, address, txid, amount):
    tx.run(CREATE_OUTPUT_REL, {"address": address, "txid": txid, "amount": amount})

def create_unknown_tx(tx, txid):
    tx.run(CREATE_UNKNOWN_TX_QUERY, {"txid": txid})

def label_seed_address(tx, address):
    tx.run(LABEL_SEED_ADDRESS_QUERY, {"address": address})

def create_address_node(tx, address):
    tx.run(CREATE_ADDRESS_QUERY, {"address": address})

def create_transaction_node(tx, txid, timestamp, block_height, fee):
    tx.run(CREATE_TX_QUERY, {
        "txid": txid,
        "timestamp": timestamp,
        "block_height": block_height,
        "fee": (fee or 0) / 100_000_000
    })

def label_service_address(tx, address):
    tx.run(LABEL_SERVICE_ADDRESS_QUERY, {"address": address})
