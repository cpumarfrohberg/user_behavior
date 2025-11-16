"""Tests for combined score calculation"""

import pytest

from evals.combined_score import calculate_combined_score

# Test constants
PERFECT_SCORE = 1.0
ZERO_SCORE = 0.0
DEFAULT_TOKENS = 1000
LOW_TOKENS = 500
HIGH_TOKENS = 5000
ZERO_TOKENS = 0
NEGATIVE_TOKENS = -100


# Fixtures
@pytest.fixture
def perfect_scores():
    """Perfect hit rate and judge score"""
    return PERFECT_SCORE, PERFECT_SCORE


@pytest.fixture
def default_tokens():
    """Default token count for testing"""
    return DEFAULT_TOKENS


# Basic Score Tests
@pytest.mark.parametrize(
    "hit_rate,judge_score,num_tokens,expected_score,check_type",
    [
        (PERFECT_SCORE, PERFECT_SCORE, DEFAULT_TOKENS, None, "greater_than_zero"),
        (ZERO_SCORE, PERFECT_SCORE, DEFAULT_TOKENS, ZERO_SCORE, "equals"),
        (PERFECT_SCORE, ZERO_SCORE, DEFAULT_TOKENS, ZERO_SCORE, "equals"),
    ],
    ids=["perfect_scores", "zero_hit_rate", "zero_judge_score"],
)
def test_calculate_combined_score_basic(
    hit_rate, judge_score, num_tokens, expected_score, check_type
):
    """Test combined score with basic scenarios"""
    score = calculate_combined_score(hit_rate, judge_score, num_tokens)

    if check_type == "greater_than_zero":
        assert score > 0
        assert isinstance(score, float)
    elif check_type == "equals":
        assert score == expected_score


# Token Penalty Tests
def test_calculate_combined_score_penalizes_tokens(perfect_scores):
    """Test that higher token usage reduces combined score"""
    hit_rate, judge_score = perfect_scores

    score_low_tokens = calculate_combined_score(hit_rate, judge_score, LOW_TOKENS)
    score_high_tokens = calculate_combined_score(hit_rate, judge_score, HIGH_TOKENS)

    assert score_low_tokens > score_high_tokens


# Custom Parameters Tests
def test_calculate_combined_score_custom_parameters(perfect_scores, default_tokens):
    """Test combined score with custom alpha, beta, gamma"""
    hit_rate, judge_score = perfect_scores

    score_default = calculate_combined_score(hit_rate, judge_score, default_tokens)
    score_custom = calculate_combined_score(
        hit_rate, judge_score, default_tokens, alpha=1.0, beta=0.5, gamma=1.0
    )

    # Scores should be different with different parameters
    assert score_default != score_custom


# Edge Cases Tests
@pytest.mark.parametrize(
    "num_tokens",
    [ZERO_TOKENS, NEGATIVE_TOKENS],
    ids=["zero_tokens", "negative_tokens"],
)
def test_calculate_combined_score_edge_case_tokens(perfect_scores, num_tokens):
    """Test combined score handles edge cases for token count"""
    hit_rate, judge_score = perfect_scores

    score = calculate_combined_score(hit_rate, judge_score, num_tokens)
    assert score > 0
    assert isinstance(score, float)
