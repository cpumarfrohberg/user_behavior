import re
from typing import Any

FORBIDDEN_KEYWORDS = ["CREATE", "DELETE", "SET", "REMOVE", "MERGE"]

JACCARD_WEIGHT = 0.7
LENGTH_PENALTY_WEIGHT = 0.3
PERFECT_SCORE = 1.0
ZERO_SCORE = 0.0
SLOW_QUERY_THRESHOLD_SECONDS = 10.0
FAST_QUERY_THRESHOLD_SECONDS = 0.1
EFFICIENCY_NORMALIZATION_EXPONENT = 0.5


def validate_cypher_query(query: str) -> bool:
    if not query or not query.strip():
        return False

    paren_count = query.count("(") - query.count(")")
    if paren_count != 0:
        return False

    bracket_count = query.count("[") - query.count("]")
    if bracket_count != 0:
        return False

    brace_count = query.count("{") - query.count("}")
    if brace_count != 0:
        return False

    return True


def check_query_safety(query: str) -> bool:
    if not query:
        return False

    query_upper = query.upper()

    for keyword in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, query_upper):
            return False

    return True


def compare_query_results(expected: list[Any], actual: list[Any]) -> float:
    if not expected and not actual:
        return PERFECT_SCORE

    if not expected or not actual:
        return ZERO_SCORE

    expected_set = {_normalize_record(record) for record in expected}
    actual_set = {_normalize_record(record) for record in actual}

    intersection = expected_set.intersection(actual_set)
    union = expected_set.union(actual_set)

    if not union:
        return ZERO_SCORE

    jaccard_similarity = len(intersection) / len(union)

    length_penalty = PERFECT_SCORE - abs(len(expected) - len(actual)) / max(
        len(expected), len(actual), 1
    )

    return (jaccard_similarity * JACCARD_WEIGHT) + (
        length_penalty * LENGTH_PENALTY_WEIGHT
    )


def _normalize_record(record: Any) -> str:
    if isinstance(record, dict):
        sorted_items = sorted(record.items())
        return str(sorted_items)
    return str(record)


def calculate_query_efficiency(query: str, execution_time: float) -> float:
    """
    Calculate query efficiency score based on execution time.

    Efficiency decreases as execution time increases.
    Uses a logarithmic scale to normalize scores.

    Args:
        query: Cypher query string
        execution_time: Query execution time in seconds

    Returns:
        Efficiency score between 0.0 and 1.0 (higher is better)
    """
    if execution_time <= 0:
        return PERFECT_SCORE

    if execution_time >= SLOW_QUERY_THRESHOLD_SECONDS:
        return ZERO_SCORE

    if execution_time <= FAST_QUERY_THRESHOLD_SECONDS:
        return PERFECT_SCORE

    normalized_time = execution_time / SLOW_QUERY_THRESHOLD_SECONDS
    efficiency = PERFECT_SCORE - (normalized_time**EFFICIENCY_NORMALIZATION_EXPONENT)

    return max(ZERO_SCORE, min(PERFECT_SCORE, efficiency))
