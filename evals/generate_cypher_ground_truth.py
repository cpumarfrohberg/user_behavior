"""
Generate ground truth dataset for Cypher Query Agent evaluation.

This module provides functions to create ground truth data by running predefined
Cypher queries against Neo4j and extracting node/question IDs from results.

Usage via CLI:
    python -m evals.generate_cypher_ground_truth
"""

import json
import logging
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

logger = logging.getLogger(__name__)


# Query definitions
QUERY_DEFINITIONS = [
    {
        "name": "user_most_questions",
        "query": """
        MATCH (u:User)-[:ASKED]->(q:Question)
        WITH u, count(q) as question_count
        ORDER BY question_count DESC
        LIMIT 1
        RETURN u.user_id, u.display_name, question_count
        """,
        "question": "Which user has asked the most questions?",
        "query_type": "aggregation",
        "followup_query_template": """
        MATCH (u:User {{user_id: {user_id}}})-[:ASKED]->(q:Question)
        RETURN q.question_id
        LIMIT 10
        """,
        "extract_sources": lambda results, driver: _extract_questions_from_user(
            results, driver
        ),
    },
    {
        "name": "questions_with_tag",
        "query": """
        MATCH (q:Question)-[:HAS_TAG]->(t:Tag {name: 'user-behavior'})
        RETURN q.question_id
        LIMIT 10
        """,
        "question": "What questions are tagged with user-behavior?",
        "query_type": "relationship_traversal",
        "extract_sources": lambda results, driver: _extract_question_ids(results),
    },
    {
        "name": "questions_with_accepted_answers",
        "query": """
        MATCH (q:Question)-[:ACCEPTED]->(a:Answer)
        RETURN q.question_id
        LIMIT 10
        """,
        "question": "What questions have accepted answers?",
        "query_type": "pattern_detection",
        "extract_sources": lambda results, driver: _extract_question_ids(results),
    },
    {
        "name": "questions_most_answers",
        "query": """
        MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
        WITH q, count(a) as answer_count
        ORDER BY answer_count DESC
        LIMIT 10
        RETURN q.question_id
        """,
        "question": "Which questions have the most answers?",
        "query_type": "aggregation",
        "extract_sources": lambda results, driver: _extract_question_ids(results),
    },
    {
        "name": "users_asked_and_answered",
        "query": """
        MATCH (u:User)-[:ASKED]->(q:Question)
        WITH u
        MATCH (u)-[:ANSWERED]->(a:Answer)
        RETURN DISTINCT u.user_id
        LIMIT 10
        """,
        "question": "Which users have both asked questions and provided answers?",
        "query_type": "pattern_detection",
        "extract_sources": lambda results, driver: _extract_questions_from_users(
            results, driver
        ),
    },
    {
        "name": "questions_text_search",
        "query": """
        MATCH (q:Question)
        WHERE q.title CONTAINS 'user' OR q.body CONTAINS 'user'
        RETURN q.question_id
        LIMIT 10
        """,
        "question": "What questions mention 'user' in their title or body?",
        "query_type": "text_search",
        "extract_sources": lambda results, driver: _extract_question_ids(results),
    },
]


def execute_cypher_query(driver: Any, query: str) -> list[dict[str, Any]]:
    """Execute a Cypher query and return results as list of dicts."""
    with driver.session(database="neo4j") as session:
        result = session.run(query)
        records = []
        for record in result:
            record_dict = {}
            for key in record.keys():
                value = record[key]
                if isinstance(value, list):
                    record_dict[key] = [
                        str(v) if hasattr(v, "__str__") else v for v in value
                    ]
                elif hasattr(value, "__str__"):
                    record_dict[key] = str(value)
                else:
                    record_dict[key] = value
            records.append(record_dict)
        return records


def _extract_question_ids(results: list[dict[str, Any]]) -> list[str]:
    """Extract question IDs from query results."""
    return [f"question_{r['question_id']}" for r in results if r.get("question_id")]


def _extract_questions_from_user(
    results: list[dict[str, Any]], driver: Any
) -> list[str]:
    """Extract question IDs for questions asked by a user."""
    if not results:
        return []
    user_id = results[0].get("user_id")
    if not user_id:
        return []

    followup_query = f"""
    MATCH (u:User {{user_id: {user_id}}})-[:ASKED]->(q:Question)
    RETURN q.question_id
    LIMIT 10
    """
    question_results = execute_cypher_query(driver, followup_query)
    sources = _extract_question_ids(question_results)
    return sources[:5]


def _extract_questions_from_users(
    results: list[dict[str, Any]], driver: Any
) -> list[str]:
    """Extract question IDs for questions asked by multiple users."""
    if not results:
        return []

    user_ids = [r.get("user_id") for r in results if r.get("user_id")]
    if not user_ids:
        return []

    user_ids_str = ",".join(map(str, user_ids[:5]))
    followup_query = f"""
    MATCH (u:User)-[:ASKED]->(q:Question)
    WHERE u.user_id IN [{user_ids_str}]
    RETURN q.question_id
    LIMIT 10
    """
    question_results = execute_cypher_query(driver, followup_query)
    return _extract_question_ids(question_results)


def _create_ground_truth_entry(
    query_def: dict[str, Any], expected_sources: list[str]
) -> dict[str, Any]:
    """Create a ground truth entry from query definition and sources."""
    return {
        "question": query_def["question"],
        "expected_sources": expected_sources,
        "query_type": query_def["query_type"],
    }


def _process_query_definition(
    query_def: dict[str, Any], driver: Any
) -> dict[str, Any] | None:
    """Process a single query definition and return ground truth entry."""
    try:
        results = execute_cypher_query(driver, query_def["query"])
        extract_fn = query_def.get("extract_sources", _extract_question_ids)
        expected_sources = extract_fn(results, driver)

        if expected_sources:
            return _create_ground_truth_entry(query_def, expected_sources)
    except Exception as e:
        logger.warning(f"Failed to generate ground truth for {query_def['name']}: {e}")
    return None


def generate_ground_truth_from_neo4j() -> list[dict[str, Any]]:
    """Generate ground truth by running predefined Cypher queries and extracting results."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        driver.verify_connectivity()
        logger.info("Connected to Neo4j successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise

    ground_truth = []
    for query_def in QUERY_DEFINITIONS:
        entry = _process_query_definition(query_def, driver)
        if entry:
            ground_truth.append(entry)

    driver.close()
    logger.info(f"Generated {len(ground_truth)} ground truth entries")
    return ground_truth


def save_cypher_ground_truth(
    ground_truth: list[dict[str, Any]],
    output_path: str | Path = "evals/cypher_ground_truth.json",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix != ".json":
        output_path = output_path.with_suffix(".json")

    with open(output_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    logger.info(f"Saved {len(ground_truth)} ground truth entries to {output_path}")
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ground_truth = generate_ground_truth_from_neo4j()
    save_cypher_ground_truth(ground_truth)
