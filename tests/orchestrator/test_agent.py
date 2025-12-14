import re

import pytest

from mongodb_agent.models import TokenUsage
from orchestrator.models import OrchestratorAgentResult, OrchestratorAnswer
from tests.orchestrator.conftest import (
    TEST_MAX_CONFIDENCE,
    TEST_MIN_AGENTS_USED,
    TEST_MIN_ANSWER_LENGTH,
    TEST_MIN_CONFIDENCE,
    TEST_MIN_REASONING_LENGTH,
    TEST_MIN_TOKEN_COUNT,
    TEST_TIMEOUT_SECONDS,
)

# Common test questions
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
    func = pytest.mark.timeout(TEST_TIMEOUT_SECONDS)(func)
    return func


def _assert_valid_orchestrator_agent_result(result: OrchestratorAgentResult) -> None:
    """Assert that result is a valid OrchestratorAgentResult with proper structure."""
    assert isinstance(result, OrchestratorAgentResult)
    assert isinstance(result.answer, OrchestratorAnswer)
    assert result.answer.answer is not None
    assert isinstance(result.answer.answer, str)
    assert len(result.answer.answer) > TEST_MIN_ANSWER_LENGTH
    assert TEST_MIN_CONFIDENCE <= result.answer.confidence <= TEST_MAX_CONFIDENCE
    assert isinstance(result.answer.agents_used, list)
    assert (
        len(result.answer.agents_used) > 0
    ), "Orchestrator should use at least one agent"
    assert isinstance(result.answer.reasoning, str)
    assert isinstance(result.answer.sources_used, (list, type(None)))


def _assert_valid_agents_used(agents_used: list[str]) -> None:
    """Assert that agents_used list is valid."""
    assert (
        len(agents_used) >= TEST_MIN_AGENTS_USED
    ), "Orchestrator should use at least one agent"
    assert all(isinstance(agent, str) for agent in agents_used)
    # Valid agent names
    valid_agents = {"mongodb_agent", "cypher_query_agent"}
    for agent in agents_used:
        assert agent in valid_agents, f"Unknown agent: {agent}"


def _assert_valid_sources(sources: list[str] | None) -> None:
    """Assert that sources are valid and match expected format (if present)."""
    if sources is None:
        return  # Sources are optional for orchestrator

    assert isinstance(sources, list)
    if len(sources) > TEST_MIN_ANSWER_LENGTH:
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
    assert (
        token_usage.input_tokens >= TEST_MIN_TOKEN_COUNT
    ), "Input tokens should be >= 0"
    assert (
        token_usage.output_tokens >= TEST_MIN_TOKEN_COUNT
    ), "Output tokens should be >= 0"
    assert (
        token_usage.total_tokens >= TEST_MIN_TOKEN_COUNT
    ), "Total tokens should be >= 0"
    assert (
        token_usage.total_tokens == token_usage.input_tokens + token_usage.output_tokens
    ), "Total tokens should equal input + output"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_orchestrator_initialization(initialized_orchestrator):
    """Test orchestrator initializes correctly."""
    assert initialized_orchestrator.agent is not None


@slow_integration
async def test_orchestrator_returns_structured_output(initialized_orchestrator):
    """Test orchestrator returns valid OrchestratorAgentResult structure."""
    result = await initialized_orchestrator.query(QUESTION_FRUSTRATION)

    _assert_valid_orchestrator_agent_result(result)


@slow_integration
async def test_orchestrator_uses_agents(initialized_orchestrator):
    """Test orchestrator uses at least one agent."""
    result = await initialized_orchestrator.query(QUESTION_SATISFACTION)

    _assert_valid_agents_used(result.answer.agents_used)


@slow_integration
async def test_orchestrator_includes_sources_when_available(initialized_orchestrator):
    """Test orchestrator includes sources when MongoDB agent is used."""
    result = await initialized_orchestrator.query(QUESTION_SATISFACTION)

    # Sources may or may not be present depending on routing
    # If MongoDB agent is used, sources should be present
    if "mongodb_agent" in result.answer.agents_used:
        _assert_valid_sources(result.answer.sources_used)


@slow_integration
async def test_orchestrator_tracks_token_usage(initialized_orchestrator):
    """Test orchestrator tracks and returns token usage."""
    result = await initialized_orchestrator.query(QUESTION_FRUSTRATION)

    assert hasattr(
        result, "token_usage"
    ), "OrchestratorAgentResult should have token_usage"
    _assert_valid_token_usage(result.token_usage)


@slow_integration
async def test_orchestrator_has_reasoning(initialized_orchestrator):
    """Test orchestrator includes reasoning about agent selection."""
    result = await initialized_orchestrator.query(QUESTION_USABILITY)

    assert result.answer.reasoning is not None
    assert isinstance(result.answer.reasoning, str)
    assert (
        len(result.answer.reasoning) > TEST_MIN_REASONING_LENGTH
    ), "Reasoning should not be empty"


@slow_integration
async def test_orchestrator_has_confidence(initialized_orchestrator):
    """Test orchestrator returns confidence score."""
    result = await initialized_orchestrator.query(QUESTION_LLM_RESPONSES)

    assert hasattr(result.answer, "confidence")
    assert TEST_MIN_CONFIDENCE <= result.answer.confidence <= TEST_MAX_CONFIDENCE
    assert isinstance(result.answer.confidence, float)


@slow_integration
async def test_orchestrator_routes_to_cypher_agent(initialized_orchestrator):
    """Test orchestrator routes graph queries to Cypher agent."""
    from cypher_agent.tools import reset_tool_call_count

    # Questions that should trigger Cypher agent
    graph_questions = [
        "What patterns lead to user frustration?",
        "Which user behaviors correlate with high engagement?",
        "What relationships exist between questions and tags?",
    ]

    for question in graph_questions:
        # Reset counter before each query to ensure clean state
        reset_tool_call_count()
        result = await initialized_orchestrator.query(question)
        _assert_valid_orchestrator_agent_result(result)
        # Should use Cypher agent (may also use MongoDB agent)
        assert "cypher_query_agent" in result.answer.agents_used


@slow_integration
async def test_orchestrator_routes_to_both_agents(initialized_orchestrator):
    complex_questions = [
        "What are common frustrations and what patterns lead to them?",
        "Show me examples of user confusion and analyze the patterns.",
    ]

    for question in complex_questions:
        result = await initialized_orchestrator.query(question)
        _assert_valid_orchestrator_agent_result(result)
        # Should use both agents
        assert len(result.answer.agents_used) >= TEST_MIN_AGENTS_USED
        # At least one agent should be used
        assert any(
            agent in result.answer.agents_used
            for agent in ["mongodb_agent", "cypher_query_agent"]
        )
