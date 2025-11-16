"""Tests for source metrics calculation"""

import pytest

from evals.source_metrics import calculate_hit_rate, calculate_mrr

# Test constants
PERFECT_HIT_RATE = 1.0
NO_HIT_RATE = 0.0
MRR_FIRST_RANK = 1.0
MRR_SECOND_RANK = 0.5
MRR_THIRD_RANK = 1.0 / 3.0


# Fixtures
@pytest.fixture
def sample_expected_sources():
    """Sample expected sources for testing"""
    return ["question_123", "question_456"]


@pytest.fixture
def sample_actual_sources():
    """Sample actual sources for testing"""
    return ["question_123", "question_789"]


# Hit Rate Tests
@pytest.mark.parametrize(
    "expected,actual,expected_hit_rate",
    [
        (
            ["question_123", "question_456"],
            ["question_123", "question_789"],
            PERFECT_HIT_RATE,
        ),
        (
            ["question_123", "question_456"],
            ["question_789", "question_999"],
            NO_HIT_RATE,
        ),
        (["question_123"], ["QUESTION_123"], PERFECT_HIT_RATE),  # Case insensitive
        ([], ["question_123"], NO_HIT_RATE),  # Empty expected
        (["question_123"], [], NO_HIT_RATE),  # Empty actual
    ],
    ids=[
        "perfect_match",
        "no_match",
        "case_insensitive",
        "empty_expected",
        "empty_actual",
    ],
)
def test_calculate_hit_rate(expected, actual, expected_hit_rate):
    """Test hit rate calculation with various scenarios"""
    assert calculate_hit_rate(expected, actual) == expected_hit_rate


# MRR Tests
@pytest.mark.parametrize(
    "expected,actual,expected_mrr,use_approx",
    [
        (["question_123"], ["question_123", "question_456"], MRR_FIRST_RANK, False),
        (["question_123"], ["question_456", "question_123"], MRR_SECOND_RANK, False),
        (
            ["question_123"],
            ["question_456", "question_789", "question_123"],
            MRR_THIRD_RANK,
            True,
        ),
        (["question_123"], ["question_456", "question_789"], NO_HIT_RATE, False),
        (["question_123"], ["QUESTION_123"], MRR_FIRST_RANK, False),  # Case insensitive
        ([], ["question_123"], NO_HIT_RATE, False),  # Empty expected
        (["question_123"], [], NO_HIT_RATE, False),  # Empty actual
        (
            ["question_123", "question_456"],
            ["question_999", "question_123", "question_456"],
            MRR_SECOND_RANK,
            False,
        ),  # Multiple expected
    ],
    ids=[
        "first_rank",
        "second_rank",
        "third_rank",
        "no_match",
        "case_insensitive",
        "empty_expected",
        "empty_actual",
        "multiple_expected",
    ],
)
def test_calculate_mrr(expected, actual, expected_mrr, use_approx):
    """Test MRR calculation with various scenarios"""
    result = calculate_mrr(expected, actual)
    if use_approx:
        assert result == pytest.approx(expected_mrr)
    else:
        assert result == expected_mrr
