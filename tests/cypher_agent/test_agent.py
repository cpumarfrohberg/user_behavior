"""Tests for Cypher Query Agent"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cypher_agent.agent import CypherQueryAgent
from cypher_agent.models import CypherAgentResult, CypherAnswer, TokenUsage
from tests.cypher_agent.conftest import (
    TEST_ANSWER,
    TEST_CONFIDENCE,
    TEST_INPUT_TOKENS,
    TEST_OUTPUT_TOKENS,
    TEST_QUERY,
    TEST_QUESTION,
    TEST_REASONING,
    TEST_TOTAL_TOKENS,
)

TEST_SOURCES = ["node_1", "node_2"]
TEST_ZERO_TOKENS = 0
TEST_CONFIDENCE_MOCK = 0.8
TEST_QUESTION_ID_1 = "question_123"
TEST_QUESTION_ID_2 = "question_456"
TEST_NODE_ID_1 = "node_1"
TEST_NODE_ID_2 = "node_456"
TEST_NODE_ID_3 = "node_789"
TEST_TAG_SURVEYS = "surveys"
TEST_TAG_RESEARCH = "research"
TEST_TAG_USER_BEHAVIOR = "user-behavior"
TEST_TAG_CONVERSION_RATE = "conversion-rate"
TEST_PLAIN_NUMBER_1 = "123"
TEST_PLAIN_NUMBER_2 = "456"
TEST_PLAIN_STRING = "plain_string"
TEST_MIN_TOOL_CALLS = 1
TEST_MAX_TOOL_CALLS = 5
TEST_TOOL_CALL_COUNT_BEFORE_RESET = 2
TEST_TOOL_CALL_COUNT_AFTER_RESET = 0


@pytest.fixture
def mock_agent_result(mock_cypher_answer):
    """Mock agent result from pydantic_ai"""
    mock_result = MagicMock()
    mock_result.output = mock_cypher_answer
    mock_usage = MagicMock()
    mock_usage.input_tokens = TEST_INPUT_TOKENS
    mock_usage.output_tokens = TEST_OUTPUT_TOKENS
    mock_result.usage = MagicMock(return_value=mock_usage)
    return mock_result


@pytest.fixture
def mock_pydantic_ai_agent(mock_agent_result, mock_agent_instance):
    """Mock pydantic_ai Agent with run method"""
    mock_agent_instance.run = AsyncMock(return_value=mock_agent_result)
    return mock_agent_instance


@pytest.fixture
def patched_agent(cypher_config, mock_neo4j_schema, mock_agent_instance):
    """Fixture that patches dependencies and returns agent and mocks"""
    with (
        patch("cypher_agent.agent.initialize_neo4j_driver") as mock_init_driver,
        patch("cypher_agent.agent.get_neo4j_schema") as mock_get_schema,
        patch("cypher_agent.agent.Agent") as mock_agent_class,
    ):
        mock_get_schema.return_value = mock_neo4j_schema
        mock_agent_class.return_value = mock_agent_instance

        agent = CypherQueryAgent(cypher_config)
        agent.initialize()

        yield (
            agent,
            {
                "init_driver": mock_init_driver,
                "get_schema": mock_get_schema,
                "agent_class": mock_agent_class,
                "agent_instance": mock_agent_instance,
            },
        )


class TestCypherQueryAgent:
    def test_initialization(self, patched_agent, cypher_config, mock_neo4j_schema):
        """Test agent initialization"""
        agent, mocks = patched_agent

        mocks["init_driver"].assert_called_once_with(
            uri=cypher_config.neo4j_uri,
            user=cypher_config.neo4j_user,
            password=cypher_config.neo4j_password,
        )
        mocks["get_schema"].assert_called_once()
        mocks["agent_class"].assert_called_once()
        assert agent.schema == mock_neo4j_schema
        assert agent.agent == mocks["agent_instance"]

    def test_schema_injection_into_instructions(self, patched_agent, mock_neo4j_schema):
        """Test that schema is injected into instructions"""
        _, mocks = patched_agent
        call_args = mocks["agent_class"].call_args
        instructions = call_args.kwargs.get("instructions", "")

        assert "{schema}" not in instructions
        assert mock_neo4j_schema in instructions or "NEO4J SCHEMA" in instructions

    @pytest.mark.asyncio
    async def test_query_success(self, patched_agent, mock_pydantic_ai_agent):
        """Test successful query execution"""
        agent, mocks = patched_agent
        mocks["agent_instance"].run = mock_pydantic_ai_agent.run

        with patch("cypher_agent.agent.log_agent_run_async"):
            result = await agent.query(TEST_QUESTION)

        assert isinstance(result, CypherAgentResult)
        assert isinstance(result.answer, CypherAnswer)
        assert result.answer.answer == TEST_ANSWER
        assert result.answer.confidence == TEST_CONFIDENCE
        assert isinstance(result.tool_calls, list)
        assert isinstance(result.token_usage, TokenUsage)
        mock_pydantic_ai_agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_not_initialized(self, cypher_config):
        """Test that query fails if agent not initialized"""
        agent = CypherQueryAgent(cypher_config)
        with pytest.raises(RuntimeError, match="not initialized"):
            await agent.query(TEST_QUESTION)

    @pytest.mark.asyncio
    async def test_query_agent_error(self, patched_agent, mock_pydantic_ai_agent):
        """Test query when agent raises an error"""
        agent, mocks = patched_agent
        mocks["agent_instance"].run = AsyncMock(side_effect=Exception("Agent error"))

        with pytest.raises(Exception, match="Agent error"):
            await agent.query(TEST_QUESTION)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "input_tokens,output_tokens,expected_total",
        [
            (TEST_INPUT_TOKENS, TEST_OUTPUT_TOKENS, TEST_TOTAL_TOKENS),
            (TEST_ZERO_TOKENS, TEST_ZERO_TOKENS, TEST_ZERO_TOKENS),
        ],
    )
    async def test_token_usage(
        self,
        patched_agent,
        mock_cypher_answer,
        input_tokens,
        output_tokens,
        expected_total,
    ):
        """Test token usage extraction (normal and fallback)"""
        agent, mocks = patched_agent

        if input_tokens == TEST_ZERO_TOKENS:
            # Fallback case
            mock_result = MagicMock()
            mock_result.output = mock_cypher_answer
            mock_result.usage.side_effect = AttributeError("No usage method")
            mocks["agent_instance"].run = AsyncMock(return_value=mock_result)
        else:
            # Normal case
            mock_usage = MagicMock()
            mock_usage.input_tokens = input_tokens
            mock_usage.output_tokens = output_tokens
            mock_result = MagicMock()
            mock_result.output = mock_cypher_answer
            mock_result.usage = MagicMock(return_value=mock_usage)
            mocks["agent_instance"].run = AsyncMock(return_value=mock_result)

        result = await agent.query(TEST_QUESTION)

        assert result.token_usage.input_tokens == input_tokens
        assert result.token_usage.output_tokens == output_tokens
        assert result.token_usage.total_tokens == expected_total


@pytest.mark.parametrize(
    "sources,expected",
    [
        (
            [TEST_QUESTION_ID_1, TEST_QUESTION_ID_2],
            [TEST_QUESTION_ID_1, TEST_QUESTION_ID_2],
        ),
        ([TEST_NODE_ID_1, TEST_NODE_ID_3], [TEST_NODE_ID_1, TEST_NODE_ID_3]),
        ([TEST_QUESTION_ID_1, TEST_NODE_ID_2], [TEST_QUESTION_ID_1, TEST_NODE_ID_2]),
        ([TEST_QUESTION_ID_1, TEST_TAG_SURVEYS], [TEST_QUESTION_ID_1]),
        (
            [TEST_QUESTION_ID_1, TEST_TAG_RESEARCH, TEST_TAG_CONVERSION_RATE],
            [TEST_QUESTION_ID_1],
        ),
        ([TEST_TAG_SURVEYS, TEST_TAG_RESEARCH], []),
        (
            [TEST_QUESTION_ID_1, TEST_TAG_USER_BEHAVIOR, TEST_NODE_ID_2],
            [TEST_QUESTION_ID_1, TEST_NODE_ID_2],
        ),
        ([], []),
        ([TEST_PLAIN_NUMBER_1, TEST_PLAIN_NUMBER_2], []),
        ([TEST_PLAIN_STRING], []),
    ],
    ids=[
        "valid_questions",
        "valid_nodes",
        "mixed_valid",
        "one_tag",
        "multiple_tags",
        "all_tags",
        "mixed_valid_invalid",
        "empty",
        "plain_numbers",
        "plain_string",
    ],
)
def test_filter_valid_sources(cypher_config, sources, expected):
    """Test that _filter_valid_sources filters out invalid sources"""
    agent = CypherQueryAgent(cypher_config)
    result = agent._filter_valid_sources(sources)
    assert result == expected


def test_extract_sources_with_filtering(
    cypher_config, mock_neo4j_schema, mock_agent_instance
):
    """Test that _extract_sources_from_result filters invalid sources"""
    with (
        patch("cypher_agent.agent.initialize_neo4j_driver"),
        patch("cypher_agent.agent.get_neo4j_schema") as mock_get_schema,
        patch("cypher_agent.agent.Agent") as mock_agent_class,
    ):
        mock_get_schema.return_value = mock_neo4j_schema
        mock_agent_class.return_value = mock_agent_instance

        agent = CypherQueryAgent(cypher_config)
        agent.initialize()

        # Create mock result with mixed valid/invalid sources
        mock_result = MagicMock()
        mock_answer = CypherAnswer(
            answer="Test answer",
            confidence=TEST_CONFIDENCE_MOCK,
            sources_used=[
                TEST_QUESTION_ID_1,
                TEST_TAG_SURVEYS,
                TEST_TAG_RESEARCH,
                TEST_NODE_ID_2,
            ],
            reasoning="Test reasoning",
            query_used="MATCH (n) RETURN n",
        )
        mock_result.output = mock_answer

        # Extract sources should filter out tag names
        sources = agent._extract_sources_from_result(mock_result)

        assert sources == [TEST_QUESTION_ID_1, TEST_NODE_ID_2]
        assert TEST_TAG_SURVEYS not in sources
        assert TEST_TAG_RESEARCH not in sources


def test_extract_sources_all_invalid(
    cypher_config, mock_neo4j_schema, mock_agent_instance
):
    """Test that _extract_sources_from_result returns empty list when all sources are invalid"""
    with (
        patch("cypher_agent.agent.initialize_neo4j_driver"),
        patch("cypher_agent.agent.get_neo4j_schema") as mock_get_schema,
        patch("cypher_agent.agent.Agent") as mock_agent_class,
    ):
        mock_get_schema.return_value = mock_neo4j_schema
        mock_agent_class.return_value = mock_agent_instance

        agent = CypherQueryAgent(cypher_config)
        agent.initialize()

        mock_result = MagicMock()
        mock_answer = CypherAnswer(
            answer="Test answer",
            confidence=TEST_CONFIDENCE_MOCK,
            sources_used=[TEST_TAG_SURVEYS, TEST_TAG_RESEARCH, TEST_TAG_USER_BEHAVIOR],
            reasoning="Test reasoning",
            query_used="MATCH (n) RETURN n",
        )
        mock_result.output = mock_answer

        sources = agent._extract_sources_from_result(mock_result)

        assert sources == []


def test_reset_and_verify_counters(
    cypher_config, mock_neo4j_schema, mock_agent_instance
):
    """Test that _reset_and_verify_counters resets tool calls and verifies counter"""
    from cypher_agent.tools import (
        _check_and_increment_tool_call_count,
        get_tool_call_count,
        reset_tool_call_count,
        set_max_tool_calls,
    )

    with (
        patch("cypher_agent.agent.initialize_neo4j_driver"),
        patch("cypher_agent.agent.get_neo4j_schema") as mock_get_schema,
        patch("cypher_agent.agent.Agent") as mock_agent_class,
    ):
        mock_get_schema.return_value = mock_neo4j_schema
        mock_agent_class.return_value = mock_agent_instance

        agent = CypherQueryAgent(cypher_config)
        agent.initialize()

        # Set up counter state
        set_max_tool_calls(TEST_MAX_TOOL_CALLS)
        reset_tool_call_count()

        # Increment counter to simulate previous query
        for _ in range(TEST_TOOL_CALL_COUNT_BEFORE_RESET):
            _check_and_increment_tool_call_count()
        assert get_tool_call_count() == TEST_TOOL_CALL_COUNT_BEFORE_RESET

        # Call reset and verify
        agent._reset_and_verify_counters()

        # Verify counter is reset
        assert get_tool_call_count() == TEST_TOOL_CALL_COUNT_AFTER_RESET


# Integration tests
@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_cypher_agent_initialization_integration(cypher_config):
    """Integration test: Cypher agent initializes with real Neo4j connection."""
    from cypher_agent.agent import CypherQueryAgent

    agent = CypherQueryAgent(cypher_config)
    try:
        agent.initialize()
        assert agent.agent is not None
        assert agent.schema is not None
        assert len(agent.schema) > 0
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_cypher_agent_pattern_detection_query(cypher_config):
    """Integration test: Cypher agent handles pattern detection queries."""
    from cypher_agent.agent import CypherQueryAgent

    agent = CypherQueryAgent(cypher_config)
    try:
        agent.initialize()
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")

    question = "What patterns lead to user frustration?"
    result = await agent.query(question)

    assert result is not None
    assert result.answer is not None
    assert isinstance(result.answer.answer, str)
    assert len(result.answer.answer) > 0


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_cypher_agent_correlation_query(cypher_config):
    """Integration test: Cypher agent handles correlation queries."""
    from cypher_agent.agent import CypherQueryAgent

    agent = CypherQueryAgent(cypher_config)
    try:
        agent.initialize()
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")

    question = "Which user behaviors correlate with high engagement?"
    result = await agent.query(question)

    assert result is not None
    assert result.answer is not None
    assert isinstance(result.answer.answer, str)
    assert len(result.answer.answer) > 0


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_cypher_agent_relationship_query(cypher_config):
    """Integration test: Cypher agent handles relationship queries."""
    from cypher_agent.agent import CypherQueryAgent

    agent = CypherQueryAgent(cypher_config)
    try:
        agent.initialize()
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")

    question = "What relationships exist between questions and tags?"
    result = await agent.query(question)

    assert result is not None
    assert result.answer is not None
    assert isinstance(result.answer.answer, str)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_cypher_agent_error_handling_invalid_query(cypher_config):
    """Integration test: Cypher agent handles invalid queries gracefully."""
    from cypher_agent.agent import CypherQueryAgent

    agent = CypherQueryAgent(cypher_config)
    try:
        agent.initialize()
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")

    # The agent should handle invalid queries gracefully
    # Note: The agent will try to generate a valid query, so we test that it doesn't crash
    question = "This is not a valid graph query format at all"
    result = await agent.query(question)

    # Should return a result (even if it indicates no answer found)
    assert result is not None
    assert result.answer is not None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_cypher_agent_schema_injection(cypher_config):
    """Integration test: Cypher agent injects schema into instructions."""
    from cypher_agent.agent import CypherQueryAgent

    agent = CypherQueryAgent(cypher_config)
    try:
        agent.initialize()
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")

    # Verify schema is retrieved and injected
    assert agent.schema is not None
    assert len(agent.schema) > 0
    # Schema should contain node/relationship information
    assert "NODE" in agent.schema.upper() or "RELATIONSHIP" in agent.schema.upper()
