import re

import pytest

from mongodb_agent.models import (
    SearchAgentResult,
    SearchAnswer,
    SearchEntry,
    TokenUsage,
)

QUESTION_FRUSTRATION = "What are common user frustration patterns?"
QUESTION_SATISFACTION = "How do users express satisfaction?"
QUESTION_USABILITY = "What usability issues do users report?"
QUESTION_LLM_RESPONSES = "examples of incorrect LLM responses"


# Common decorators for slow integration tests
def slow_integration(func):
    """Decorator for slow integration tests."""
    func = pytest.mark.asyncio(func)
    func = pytest.mark.integration(func)
    func = pytest.mark.slow(func)
    func = pytest.mark.timeout(120)(func)
    return func


def _assert_valid_search_agent_result(result: SearchAgentResult) -> None:
    """Assert that result is a valid SearchAgentResult with proper structure."""
    assert isinstance(result, SearchAgentResult)
    assert isinstance(result.answer, SearchAnswer)
    assert result.answer.answer is not None
    assert isinstance(result.answer.answer, str)
    assert len(result.answer.answer) > 0
    assert 0.0 <= result.answer.confidence <= 1.0
    assert isinstance(result.answer.sources_used, list)
    assert isinstance(result.answer.reasoning, (str, type(None)))
    assert isinstance(result.tool_calls, list)


def _assert_valid_tool_calls(
    tool_calls: list[dict], expected_tool_name: str = "search_mongodb"
) -> None:
    """Assert that tool calls are valid and use the expected tool."""
    assert len(tool_calls) > 0, "Tool calls should be tracked"
    for call in tool_calls:
        assert "tool_name" in call, "Tool call should have tool_name"
        assert "args" in call, "Tool call should have args"
        assert (
            call["tool_name"] == expected_tool_name
        ), f"Expected {expected_tool_name}, got {call['tool_name']}"


def _assert_valid_sources(sources: list[str]) -> None:
    """Assert that sources are valid and match expected format."""
    assert len(sources) > 0, "Agent should include sources"
    assert all(isinstance(source, str) for source in sources)

    # Validate source format: "question_{numeric_id}"
    source_pattern = re.compile(r"^question_\d+$")
    for source in sources:
        assert source_pattern.match(
            source
        ), f"Source '{source}' should match pattern 'question_<id>'"


def _assert_valid_token_usage(token_usage: TokenUsage) -> None:
    """Assert that token usage is valid."""
    assert token_usage is not None, "token_usage should not be None"
    assert isinstance(token_usage, TokenUsage)
    assert token_usage.input_tokens >= 0, "Input tokens should be >= 0"
    assert token_usage.output_tokens >= 0, "Output tokens should be >= 0"
    assert token_usage.total_tokens >= 0, "Total tokens should be >= 0"
    assert (
        token_usage.total_tokens == token_usage.input_tokens + token_usage.output_tokens
    ), "Total tokens should equal input + output"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_initialization(initialized_agent):
    assert initialized_agent.agent is not None
    assert initialized_agent.collection is not None


@slow_integration
@pytest.mark.parametrize(
    "question,min_calls,max_calls",
    [
        (QUESTION_FRUSTRATION, 1, 3),
        (QUESTION_LLM_RESPONSES, 0, 3),
    ],
)
async def test_agent_tool_call_count(
    initialized_agent, question: str, min_calls: int, max_calls: int
):
    """Test agent makes tool calls within expected range."""
    result = await initialized_agent.query(question)

    assert (
        min_calls <= len(result.tool_calls) <= max_calls
    ), f"Expected {min_calls}-{max_calls} tool calls, got {len(result.tool_calls)}"

    _assert_valid_tool_calls(result.tool_calls)


@slow_integration
async def test_agent_returns_structured_output(initialized_agent):
    result = await initialized_agent.query(QUESTION_FRUSTRATION)

    _assert_valid_search_agent_result(result)


@slow_integration
async def test_agent_includes_sources(initialized_agent):
    result = await initialized_agent.query(QUESTION_SATISFACTION)

    _assert_valid_sources(result.answer.sources_used)


@slow_integration
async def test_tool_calls_are_tracked(initialized_agent):
    result = await initialized_agent.query(QUESTION_USABILITY)

    _assert_valid_tool_calls(result.tool_calls)


@slow_integration
async def test_agent_tracks_token_usage(initialized_agent):
    result = await initialized_agent.query(QUESTION_FRUSTRATION)

    assert hasattr(result, "token_usage"), "SearchAgentResult should have token_usage"
    _assert_valid_token_usage(result.token_usage)
