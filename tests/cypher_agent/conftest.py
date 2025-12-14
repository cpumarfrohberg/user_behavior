"""Test fixtures for Cypher Query Agent tests"""

from unittest.mock import MagicMock

import pytest

from cypher_agent.config import CypherAgentConfig
from cypher_agent.models import CypherAgentResult, CypherAnswer, TokenUsage

TEST_QUESTION = "How many users are in the database?"
TEST_QUERY = "MATCH (u:User) RETURN count(u) as user_count"
TEST_ANSWER = "There are 100 users in the database."
TEST_CONFIDENCE = 0.85
TEST_REASONING = "The query counted all User nodes in the graph."
TEST_INPUT_TOKENS = 100
TEST_OUTPUT_TOKENS = 50
TEST_TOTAL_TOKENS = TEST_INPUT_TOKENS + TEST_OUTPUT_TOKENS
TEST_SOURCE_NODE_1 = "node_1"
TEST_SOURCE_NODE_2 = "node_2"


@pytest.fixture
def cypher_config():
    """CypherAgentConfig for testing"""
    return CypherAgentConfig()


@pytest.fixture
def mock_cypher_answer():
    """Mock CypherAnswer for testing"""
    return CypherAnswer(
        answer=TEST_ANSWER,
        confidence=TEST_CONFIDENCE,
        sources_used=[TEST_SOURCE_NODE_1, TEST_SOURCE_NODE_2],
        reasoning=TEST_REASONING,
        query_used=TEST_QUERY,
    )


@pytest.fixture
def mock_cypher_result(mock_cypher_answer):
    """Mock CypherAgentResult for testing"""
    return CypherAgentResult(
        answer=mock_cypher_answer,
        tool_calls=[
            {
                "tool_name": "execute_cypher_query",
                "args": {"query": "MATCH (n) RETURN n"},
            }
        ],
        token_usage=TokenUsage(
            input_tokens=TEST_INPUT_TOKENS,
            output_tokens=TEST_OUTPUT_TOKENS,
            total_tokens=TEST_TOTAL_TOKENS,
        ),
    )


@pytest.fixture
def mock_neo4j_schema():
    """Mock Neo4j schema string"""
    return """NEO4J SCHEMA
==================================================

NODE LABELS:
  - User
    Properties:
      - user_id: Integer
      - display_name: String
  - Question
    Properties:
      - question_id: Integer
      - title: String
      - body: String

RELATIONSHIP TYPES:
  - ASKED
  - ANSWERED
  - HAS_TAG
"""


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver"""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    driver.verify_connectivity = MagicMock()
    return driver


@pytest.fixture
def mock_agent_instance():
    """Mock pydantic_ai Agent instance"""
    agent = MagicMock()
    agent.name = "cypher_query_agent"
    return agent


@pytest.fixture
def initialized_agent(cypher_config, mock_neo4j_schema, mock_agent_instance):
    """Fixture that creates and initializes a CypherQueryAgent with all mocks"""
    from unittest.mock import patch

    with (
        patch("cypher_agent.agent.initialize_neo4j_driver"),
        patch("cypher_agent.agent.get_neo4j_schema") as mock_get_schema,
        patch("cypher_agent.agent.Agent") as mock_agent_class,
    ):
        mock_get_schema.return_value = mock_neo4j_schema
        mock_agent_class.return_value = mock_agent_instance

        from cypher_agent.agent import CypherQueryAgent

        agent = CypherQueryAgent(cypher_config)
        agent.initialize()
        yield agent, mock_agent_instance
