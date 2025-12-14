"""Tests for Cypher Query Agent"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cypher_agent.agent import CypherQueryAgent
from cypher_agent.models import CypherAgentResult, CypherAnswer, TokenUsage

TEST_QUESTION = "How many users are in the database?"
TEST_QUERY = "MATCH (u:User) RETURN count(u) as user_count"
TEST_ANSWER = "There are 100 users in the database."
TEST_CONFIDENCE = 0.85
TEST_REASONING = "The query counted all User nodes in the graph."
TEST_SOURCES = ["node_1", "node_2"]
TEST_INPUT_TOKENS = 100
TEST_OUTPUT_TOKENS = 50
TEST_TOTAL_TOKENS = TEST_INPUT_TOKENS + TEST_OUTPUT_TOKENS
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

        result = await agent.query(TEST_QUESTION)

        assert isinstance(result, CypherAgentResult)
        assert isinstance(result.answer, CypherAnswer)
        assert result.answer.answer == TEST_ANSWER
        assert result.answer.confidence == TEST_CONFIDENCE
        assert len(result.tool_calls) > 0
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
