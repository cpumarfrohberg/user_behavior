"""Tests for LLM-as-a-Judge evaluation"""

import pytest

from evals.judge import evaluate_answer
from mongodb_agent.models import SearchAnswer

# Test constants
TEST_QUESTION = "What are common user frustration patterns?"
TEST_ANSWER = "Common user frustration patterns include asking users for personal information without clear explanations, using confusing button designs, and failing to provide transparent communication."
TEST_CONFIDENCE = 0.9
TEST_SOURCES = ["question_79188", "question_3791"]
TEST_REASONING = "Found relevant discussions about user frustration patterns"
MIN_SCORE = 0.0
MAX_SCORE = 1.0
MIN_REASONING_LENGTH = 10


@pytest.fixture
def test_question():
    """Test question for judge evaluation"""
    return TEST_QUESTION


@pytest.fixture
def test_answer():
    """Test SearchAnswer for judge evaluation"""
    return SearchAnswer(
        answer=TEST_ANSWER,
        confidence=TEST_CONFIDENCE,
        sources_used=TEST_SOURCES,
        reasoning=TEST_REASONING,
    )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_judge_evaluates_answer(test_question, test_answer):
    """Test that judge evaluates answer and returns structured output"""
    result = await evaluate_answer(test_question, test_answer)

    # Verify result structure
    assert hasattr(result, "evaluation")
    assert hasattr(result, "usage")

    # Verify evaluation structure
    evaluation = result.evaluation
    assert (
        evaluation.overall_score >= MIN_SCORE and evaluation.overall_score <= MAX_SCORE
    )
    assert evaluation.accuracy >= MIN_SCORE and evaluation.accuracy <= MAX_SCORE
    assert evaluation.completeness >= MIN_SCORE and evaluation.completeness <= MAX_SCORE
    assert evaluation.relevance >= MIN_SCORE and evaluation.relevance <= MAX_SCORE
    assert isinstance(evaluation.reasoning, str)
    assert len(evaluation.reasoning) >= MIN_REASONING_LENGTH

    # Verify usage information
    usage = result.usage
    assert usage.input_tokens >= 0
    assert usage.output_tokens >= 0
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_judge_output_structure(test_question, test_answer):
    """Test that judge output has correct structure"""
    result = await evaluate_answer(test_question, test_answer)

    # Verify result structure
    assert hasattr(result, "evaluation")
    assert hasattr(result, "usage")

    # Verify all required fields are present in evaluation
    evaluation = result.evaluation
    assert hasattr(evaluation, "overall_score")
    assert hasattr(evaluation, "accuracy")
    assert hasattr(evaluation, "completeness")
    assert hasattr(evaluation, "relevance")
    assert hasattr(evaluation, "reasoning")

    # Verify usage structure
    usage = result.usage
    assert hasattr(usage, "input_tokens")
    assert hasattr(usage, "output_tokens")
    assert hasattr(usage, "total_tokens")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_judge_scores_in_range(test_question, test_answer):
    """Test that all judge scores are in valid range (0.0 to 1.0)"""
    result = await evaluate_answer(test_question, test_answer)

    evaluation = result.evaluation
    assert MIN_SCORE <= evaluation.overall_score <= MAX_SCORE
    assert MIN_SCORE <= evaluation.accuracy <= MAX_SCORE
    assert MIN_SCORE <= evaluation.completeness <= MAX_SCORE
    assert MIN_SCORE <= evaluation.relevance <= MAX_SCORE


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_judge_with_expected_sources(test_question, test_answer):
    """Test that judge can evaluate with expected sources"""
    expected_sources = ["question_79188"]

    result = await evaluate_answer(
        test_question, test_answer, expected_sources=expected_sources
    )

    # Verify evaluation still works with expected sources
    assert result.evaluation.overall_score >= MIN_SCORE
    assert result.evaluation.overall_score <= MAX_SCORE


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_judge_with_tool_calls(test_question, test_answer):
    """Test that judge can evaluate with tool calls context"""
    tool_calls = [
        {
            "tool_name": "search_mongodb",
            "args": {"query": "user frustration patterns"},
        }
    ]

    result = await evaluate_answer(test_question, test_answer, tool_calls=tool_calls)

    # Verify evaluation still works with tool calls
    assert result.evaluation.overall_score >= MIN_SCORE
    assert result.evaluation.overall_score <= MAX_SCORE
