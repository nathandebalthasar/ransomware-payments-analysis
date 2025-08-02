import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

def get_driver():
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    try:
        return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Neo4j: {e}")
