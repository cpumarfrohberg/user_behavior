"""Minimal tests for orchestrator.tools module"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.tools import (
    AgentManager,
    call_cypher_query_agent,
    call_mongodb_agent,
    cypher_manager,
    mongodb_manager,
)

TEST_QUESTION = "test question"
TEST_ANSWER = "Test answer"
TEST_MONGODB_ANSWER = "MongoDB answer"
TEST_CYPHER_ANSWER = "Cypher answer"
TEST_REASONING = "Test reasoning"
TEST_MONGODB_REASONING = "MongoDB reasoning"
TEST_CYPHER_REASONING = "Cypher reasoning"
TEST_SOURCE = "source1"
TEST_MONGODB_SOURCE = "question_123"
TEST_CYPHER_SOURCE = "node_1"
TEST_AGENT_NAME = "test_agent"
TEST_CONFIDENCE = 0.8
TEST_MONGODB_CONFIDENCE = 0.9
TEST_CYPHER_CONFIDENCE = 0.85
TEST_MONGODB_TOOL_CALLS = 2
TEST_CYPHER_TOOL_CALLS = 1
TEST_ERROR_MESSAGE = "Test error"
TEST_AGENT_DISPLAY_NAME = "Test Agent"


@pytest.fixture
def mock_agent_result():
    mock_result = MagicMock()
    mock_result.answer = MagicMock()
    mock_result.answer.answer = TEST_ANSWER
    mock_result.answer.confidence = TEST_CONFIDENCE
    mock_result.answer.sources_used = [
        TEST_SOURCE
    ]  # mimics the Pydantic model structure, where sources_used is always a list.
    mock_result.answer.reasoning = TEST_REASONING
    mock_result.tool_calls = [{"tool_name": "test_tool"}]
    return mock_result


@pytest.fixture
def mock_agent(mock_agent_result):
    mock = MagicMock()
    mock.query = AsyncMock(return_value=mock_agent_result)
    return mock


@pytest.fixture
def mock_config():
    return MagicMock()


@pytest.fixture
def agent_manager(mock_agent, mock_config):
    """Fixture for AgentManager with mocked dependencies"""

    def create_agent(config):
        return mock_agent

    def format_result(result):
        return {
            "answer": result.answer.answer,
            "confidence": result.answer.confidence,
            "sources_used": result.answer.sources_used,
            "reasoning": result.answer.reasoning,
            "tool_calls": len(result.tool_calls),
            "agent": TEST_AGENT_NAME,
        }

    return AgentManager(
        agent_name=TEST_AGENT_DISPLAY_NAME,
        agent_class=type(mock_agent),
        config_class=type(mock_config),
        create_agent=create_agent,
        format_result=format_result,
    )


@pytest.mark.asyncio
async def test_agent_manager_initialization(agent_manager, mock_agent):
    """Test AgentManager can initialize and call an agent"""
    result = await agent_manager.call(TEST_QUESTION)

    assert result["answer"] == TEST_ANSWER
    assert result["confidence"] == TEST_CONFIDENCE
    assert result["agent"] == TEST_AGENT_NAME
    mock_agent.query.assert_called_once_with(TEST_QUESTION)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call_function,manager_name,expected_answer,expected_confidence,expected_agent,expected_sources,expected_reasoning,expected_tool_calls",
    [
        (
            call_mongodb_agent,
            "mongodb_manager",
            TEST_MONGODB_ANSWER,
            TEST_MONGODB_CONFIDENCE,
            "mongodb_agent",
            [TEST_MONGODB_SOURCE],
            TEST_MONGODB_REASONING,
            TEST_MONGODB_TOOL_CALLS,
        ),
        (
            call_cypher_query_agent,
            "cypher_manager",
            TEST_CYPHER_ANSWER,
            TEST_CYPHER_CONFIDENCE,
            "cypher_query_agent",
            [TEST_CYPHER_SOURCE],
            TEST_CYPHER_REASONING,
            TEST_CYPHER_TOOL_CALLS,
        ),
    ],
)
async def test_agent_call_returns_correct_format(
    call_function,
    manager_name,
    expected_answer,
    expected_confidence,
    expected_agent,
    expected_sources,
    expected_reasoning,
    expected_tool_calls,
):
    """Test agent call functions return properly formatted dict"""
    managers = {
        "mongodb_manager": mongodb_manager,
        "cypher_manager": cypher_manager,
    }
    manager = managers[manager_name]

    mock_return_value = {
        "answer": expected_answer,
        "confidence": expected_confidence,
        "sources_used": expected_sources,
        "reasoning": expected_reasoning,
        "tool_calls": expected_tool_calls,
        "agent": expected_agent,
    }

    with patch.object(manager, "call", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_return_value

        result = await call_function(TEST_QUESTION)

        assert result["answer"] == expected_answer
        assert result["confidence"] == expected_confidence
        assert result["agent"] == expected_agent
        assert result["sources_used"] == expected_sources
        assert result["reasoning"] == expected_reasoning
        assert result["tool_calls"] == expected_tool_calls


@pytest.mark.asyncio
async def test_agent_manager_handles_errors():
    """Test AgentManager properly handles and re-raises errors"""
    mock_agent = MagicMock()
    mock_agent.query = AsyncMock(side_effect=ValueError(TEST_ERROR_MESSAGE))

    def create_agent(config):
        return mock_agent

    def format_result(result):
        return {}

    manager = AgentManager(
        agent_name=TEST_AGENT_DISPLAY_NAME,
        agent_class=type(mock_agent),
        config_class=type(MagicMock()),
        create_agent=create_agent,
        format_result=format_result,
    )

    with pytest.raises(RuntimeError, match=f"{TEST_AGENT_DISPLAY_NAME} failed"):
        await manager.call(TEST_QUESTION)
