"""
Generate ground truth dataset for chunking parameter evaluation.

This module provides functions to create ground truth data by sampling questions
from MongoDB and using their titles as queries. The correct document source is known
since we're using the question's own title/content.

Usage via CLI:
    ask generate-ground-truth --samples 50 --output ground_truth.json
"""

import json
from pathlib import Path

from pymongo import MongoClient

from config import (
    DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH,
    DEFAULT_GROUND_TRUTH_SAMPLES,
    MONGODB_COLLECTION,
    MONGODB_DB,
    MONGODB_URI,
)


def generate_ground_truth_from_mongodb(
    n_samples: int = DEFAULT_GROUND_TRUTH_SAMPLES,
    min_title_length: int = DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH,
) -> list[dict[str, str]]:
    """
    Generate ground truth by using question titles as queries.

    Args:
        n_samples: Number of samples to generate
        min_title_length: Minimum title length to include

    Returns:
        List of ground truth dicts with 'question' and 'source' keys
    """
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    collection = db[MONGODB_COLLECTION]

    # Sample random questions with valid titles
    pipeline = [
        {
            "$match": {
                "title": {"$exists": True, "$ne": ""},
                "$expr": {"$gt": [{"$strLenCP": "$title"}, min_title_length]},
            }
        },
        {"$sample": {"size": n_samples}},
        {"$project": {"_id": 0, "question_id": 1, "title": 1, "body": 1}},
    ]

    questions = list(collection.aggregate(pipeline))

    ground_truth = []
    for q in questions:
        # Use title as query (natural language question)
        question_text = q.get("title", "").strip()

        # Fallback to first sentence of body if no title
        if not question_text and q.get("body"):
            question_text = q["body"].split(".")[0].strip()

        if question_text:
            ground_truth.append(
                {
                    "question": question_text,
                    "source": f"question_{q['question_id']}",
                }
            )

    client.close()

    return ground_truth


def save_ground_truth(
    ground_truth: list[dict[str, str]],
    output_path: str | Path,
) -> None:
    """
    Save ground truth to JSON file.

    Args:
        ground_truth: List of ground truth dicts
        output_path: Path to output file (should end with .json)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure .json extension
    if output_path.suffix != ".json":
        output_path = output_path.with_suffix(".json")

    with open(output_path, "w") as f:
        json.dump(ground_truth, f, indent=2)
