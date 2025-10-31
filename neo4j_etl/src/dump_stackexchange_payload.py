"""Load StackExchange data from MongoDB into Neo4j as knowledge graph"""

import logging
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
def load_stackexchange_graph_from_mongodb() -> None:
    """
    Load StackExchange data from MongoDB into Neo4j as knowledge graph

    1. Connect to MongoDB and Neo4j
    2. Read all documents from MongoDB collection
    3. Create constraints
    4. Create nodes and relationships in batches (single transaction per batch)
    5. Log progress
    """
    # Connect to MongoDB
    LOGGER.info("Connecting to MongoDB...")
    mongo_client = MongoClient(MONGODB_URI)
    mongo_db = mongo_client[MONGODB_DB]
    mongo_collection = mongo_db[MONGODB_COLLECTION]

    # Connect to Neo4j
    LOGGER.info("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

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
    load_stackexchange_graph_from_mongodb()
