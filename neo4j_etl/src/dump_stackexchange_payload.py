"""Load StackExchange data from MongoDB into Neo4j as knowledge graph"""

import logging
import os
from typing import Any

from neo4j import GraphDatabase
from pymongo import MongoClient
from retry import retry

from config import (
    MONGODB_COLLECTION,
    MONGODB_DB,
    MONGODB_URI,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
)
from neo4j_etl.src.extract import collect_batch_data
from neo4j_etl.src.inject import NODE_LABELS, process_batch, set_uniqueness_constraints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

LOGGER = logging.getLogger(__name__)

# Batch size for processing
BATCH_SIZE = 75  # 50-100 questions per transaction


@retry(tries=100, delay=10)
def load_stackexchange_graph_from_mongodb(
    mongo_db_name: str | None = None,
    mongo_collection_name: str | None = None,
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
) -> None:
    """
    Load StackExchange data from MongoDB into Neo4j as knowledge graph

    Args:
        mongo_db_name: MongoDB database name (defaults to MONGODB_DB from config)
        mongo_collection_name: MongoDB collection name (defaults to MONGODB_COLLECTION from config)
        neo4j_uri: Neo4j URI (defaults to NEO4J_URI from config, supports cloud URIs like bolt://host:port)
        neo4j_user: Neo4j username (defaults to NEO4J_USER from config)
        neo4j_password: Neo4j password (defaults to NEO4J_PASSWORD from config)

    1. Connect to MongoDB and Neo4j
    2. Read all documents from MongoDB collection
    3. Create constraints
    4. Create nodes and relationships in batches (single transaction per batch)
    5. Log progress
    """
    # Use provided values or fall back to config/environment variables
    db_name = mongo_db_name or MONGODB_DB
    collection_name = mongo_collection_name or MONGODB_COLLECTION
    neo4j_uri_final = neo4j_uri or os.getenv("NEO4J_URI", NEO4J_URI)
    neo4j_user_final = neo4j_user or os.getenv("NEO4J_USER", NEO4J_USER)
    neo4j_password_final = neo4j_password or os.getenv("NEO4J_PASSWORD", NEO4J_PASSWORD)

    # Connect to MongoDB
    LOGGER.info(f"Connecting to MongoDB at {MONGODB_URI}...")
    LOGGER.info(f"Using database: {db_name}, collection: {collection_name}")
    mongo_client = MongoClient(MONGODB_URI)
    mongo_db = mongo_client[db_name]
    mongo_collection = mongo_db[collection_name]

    # Connect to Neo4j
    LOGGER.info(f"Connecting to Neo4j at {neo4j_uri_final}...")
    driver = GraphDatabase.driver(
        neo4j_uri_final, auth=(neo4j_user_final, neo4j_password_final)
    )

    try:
        # Create uniqueness constraints
        LOGGER.info("Setting uniqueness constraints on nodes")
        with driver.session(database="neo4j") as session:
            for node_label in NODE_LABELS:
                session.execute_write(set_uniqueness_constraints, node_label)

        # Read all questions from MongoDB
        LOGGER.info("Reading questions from MongoDB...")
        questions = list(mongo_collection.find())
        total_questions = len(questions)
        LOGGER.info(f"Found {total_questions} questions to process")

        if not questions:
            LOGGER.warning("No questions found in MongoDB")
            return

        # Process in batches
        batch_count = 0
        for i in range(0, total_questions, BATCH_SIZE):
            batch = questions[i : i + BATCH_SIZE]
            batch_count += 1
            LOGGER.info(
                f"Processing batch {batch_count} ({len(batch)} questions) - "
                f"Progress: {i + len(batch)}/{total_questions}"
            )

            try:
                # Collect all data for this batch
                batch_data = collect_batch_data(batch)

                # Process entire batch in a single transaction
                with driver.session(database="neo4j") as session:
                    session.execute_write(process_batch, batch_data)

                LOGGER.info(
                    f"Batch {batch_count} completed: "
                    f"{len(batch_data.get('questions', []))} questions, "
                    f"{len(batch_data.get('users', []))} users, "
                    f"{len(batch_data.get('tags', []))} tags, "
                    f"{len(batch_data.get('answers', []))} answers, "
                    f"{len(batch_data.get('comments', []))} comments"
                )

            except Exception as e:
                LOGGER.error(f"Error processing batch {batch_count}: {e}")
                continue

        LOGGER.info(f"Successfully processed {total_questions} questions")

    finally:
        mongo_client.close()
        driver.close()
        LOGGER.info("Connections closed")


if __name__ == "__main__":
    import sys

    # Allow command-line arguments for database and collection
    mongo_db = None
    mongo_collection = None
    neo4j_uri = None
    neo4j_user = None
    neo4j_password = None

    # Parse simple command-line args (optional)
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--db="):
                mongo_db = arg.split("=", 1)[1]
            elif arg.startswith("--collection="):
                mongo_collection = arg.split("=", 1)[1]
            elif arg.startswith("--neo4j-uri="):
                neo4j_uri = arg.split("=", 1)[1]
            elif arg.startswith("--neo4j-user="):
                neo4j_user = arg.split("=", 1)[1]
            elif arg.startswith("--neo4j-password="):
                neo4j_password = arg.split("=", 1)[1]

    load_stackexchange_graph_from_mongodb(
        mongo_db_name=mongo_db,
        mongo_collection_name=mongo_collection,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
    )
