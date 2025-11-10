"""Source metrics calculation for evaluation"""

from typing import Sequence


def calculate_hit_rate(
    expected_sources: Sequence[str], actual_sources: Sequence[str]
) -> float:
    """
    Calculate hit rate: whether at least one expected source is found.

    Args:
        expected_sources: List of expected source identifiers
        actual_sources: List of actual source identifiers from agent

    Returns:
        Hit rate: 1.0 if at least one expected source found, 0.0 otherwise
    """
    if not expected_sources:
        return 0.0

    # Normalize source names (case-insensitive comparison)
    expected_normalized = {s.lower().strip() for s in expected_sources}
    actual_normalized = {s.lower().strip() for s in actual_sources}

    # Check if any expected source is in actual sources
    return 1.0 if expected_normalized.intersection(actual_normalized) else 0.0


def calculate_mrr(
    expected_sources: Sequence[str], actual_sources: Sequence[str]
) -> float:
    """
    Calculate Mean Reciprocal Rank (MRR).

    MRR is the average of 1/rank of the first expected source found.
    If no expected source is found, MRR is 0.0.

    Args:
        expected_sources: List of expected source identifiers
        actual_sources: List of actual source identifiers from agent (in order)

    Returns:
        MRR: 1/rank of first expected source found, or 0.0 if not found
    """
    if not expected_sources or not actual_sources:
        return 0.0

    expected_normalized = {s.lower().strip() for s in expected_sources}

    # Find the rank of the first expected source in actual sources
    for rank, actual_source in enumerate(actual_sources, start=1):
        if actual_source.lower().strip() in expected_normalized:
            return 1.0 / rank

    # No expected source found
    return 0.0
