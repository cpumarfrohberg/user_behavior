"""Tests for Cypher Query Agent tools"""

from unittest.mock import MagicMock, patch

import pytest

from cypher_agent.tools import (
    _check_and_increment_tool_call_count,
    execute_cypher_query,
    get_neo4j_driver,
    get_neo4j_schema,
    get_tool_call_count,
    initialize_neo4j_driver,
    reset_tool_call_count,
    set_max_tool_calls,
    validate_cypher_query,
)
from mongodb_agent.tools import ToolCallLimitExceeded


@pytest.mark.parametrize(
    "query,expected_valid",
    [
        ("MATCH (n:User) RETURN n LIMIT 10", True),
        (
            "MATCH (q:Question)-[:HAS_TAG]->(t:Tag) WHERE t.name = 'user-behavior' RETURN q",
            True,
        ),
        (
            "MATCH (u:User)-[:ASKED]->(q:Question) WITH u, count(q) as question_count RETURN u, question_count",
            True,
        ),
        ("CREATE (n:User {name: 'test'}) RETURN n", False),
        ("MATCH (n:User) DELETE n", False),
        ("MATCH (n:User) SET n.name = 'test' RETURN n", False),
        ("MERGE (n:User {id: 1}) RETURN n", False),
        ("MATCH (u:User)-[:ASKED]->(q:Question) RETURN u, count(q) GROUP BY u", False),
        ("", False),
        ("   \n\t  ", False),
        ("MATCH (n:User RETURN n", False),
        ("MATCH (n:User)-[:ASKED->(q:Question) RETURN n", False),
        ("MATCH (n:User {name: 'test') RETURN n", False),
    ],
)
def test_validate_cypher_query(query, expected_valid):
    is_valid, error = validate_cypher_query(query)
    assert is_valid == expected_valid
    if not expected_valid:
        assert error is not None


@patch("cypher_agent.tools.GraphDatabase")
def test_initialize_neo4j_driver(mock_graph_db, mock_neo4j_driver):
    mock_graph_db.driver.return_value = mock_neo4j_driver
    initialize_neo4j_driver("bolt://localhost:7687", "neo4j", "password")
    mock_graph_db.driver.assert_called_once_with(
        "bolt://localhost:7687", auth=("neo4j", "password")
    )
    mock_neo4j_driver.verify_connectivity.assert_called_once()


@patch("cypher_agent.tools._neo4j_driver", None)
def test_get_neo4j_driver_not_initialized():
    with pytest.raises(RuntimeError, match="not initialized"):
        get_neo4j_driver()


def test_get_neo4j_driver_initialized(mock_neo4j_driver):
    with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
        assert get_neo4j_driver() == mock_neo4j_driver


def test_get_schema_success(mock_neo4j_driver, mock_neo4j_schema):
    session = mock_neo4j_driver.session.return_value.__enter__.return_value
    mock_record = MagicMock()
    mock_record.get.side_effect = lambda key, default=None: {
        "nodeLabels": ["User"],
        "relType": "ASKED",
        "propertyName": "user_id",
        "propertyTypes": ["Integer"],
    }.get(key, default)
    session.run.return_value = [mock_record]

    with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
        schema = get_neo4j_schema()

    assert "NEO4J SCHEMA" in schema
    session.run.assert_called_once_with("CALL db.schema.nodeTypeProperties()")


def test_get_schema_connection_error(mock_neo4j_driver):
    session = mock_neo4j_driver.session.return_value.__enter__.return_value
    session.run.side_effect = Exception("Connection failed")

    with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
        schema = get_neo4j_schema()

    assert "Schema retrieval failed" in schema


def test_execute_valid_query(mock_neo4j_driver):
    session = mock_neo4j_driver.session.return_value.__enter__.return_value
    mock_record = MagicMock()
    mock_record.keys.return_value = ["user_id", "display_name"]
    mock_record.__getitem__.side_effect = lambda key: {
        "user_id": 1,
        "display_name": "TestUser",
    }[key]
    session.run.return_value = [mock_record]

    with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
        result = execute_cypher_query(
            "MATCH (u:User) RETURN u.user_id, u.display_name LIMIT 1"
        )

    assert result["error"] is None
    assert len(result["results"]) == 1
    assert result["results"][0]["user_id"] == "1"
    assert result["results"][0]["display_name"] == "TestUser"


def test_execute_invalid_query(mock_neo4j_driver):
    with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
        result = execute_cypher_query("CREATE (n:User) RETURN n")

    assert result["error"] is not None
    assert result["results"] == []


@pytest.mark.parametrize(
    "exception_class,error_keyword,query",
    [
        ("CypherSyntaxError", "syntax", "MATCH (n:User) RETURN n INVALID_KEYWORD"),
        ("ServiceUnavailable", "unavailable", "MATCH (n:User) RETURN n LIMIT 10"),
    ],
)
def test_execute_query_errors(mock_neo4j_driver, exception_class, error_keyword, query):
    from neo4j.exceptions import CypherSyntaxError, ServiceUnavailable

    session = mock_neo4j_driver.session.return_value.__enter__.return_value
    session.run.side_effect = {
        "CypherSyntaxError": CypherSyntaxError("Invalid syntax"),
        "ServiceUnavailable": ServiceUnavailable("Service unavailable"),
    }[exception_class]

    with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
        result = execute_cypher_query(query)

    assert result["error"] is not None
    assert error_keyword in result["error"].lower()
    assert result["results"] == []


def test_execute_query_empty_results(mock_neo4j_driver):
    session = mock_neo4j_driver.session.return_value.__enter__.return_value
    session.run.return_value = []

    with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
        result = execute_cypher_query("MATCH (n:User) WHERE n.user_id = 99999 RETURN n")

    assert result["error"] is None
    assert result["results"] == []


@pytest.fixture
def reset_counter():
    reset_tool_call_count()
    yield
    reset_tool_call_count()


@pytest.fixture
def setup_limit(reset_counter):
    set_max_tool_calls(5)
    reset_tool_call_count()
    yield
    reset_tool_call_count()


def test_reset_tool_call_count(setup_limit):
    _check_and_increment_tool_call_count()
    _check_and_increment_tool_call_count()
    assert get_tool_call_count() == 2
    reset_tool_call_count()
    assert get_tool_call_count() == 0


@pytest.mark.parametrize("num_calls", [1, 2, 3])
def test_check_and_increment_tool_call_count(setup_limit, num_calls):
    for i in range(num_calls):
        assert _check_and_increment_tool_call_count() == i + 1
        assert get_tool_call_count() == i + 1


@pytest.mark.parametrize("limit", [2, 3, 5])
def test_tool_call_limit_exceeded(reset_counter, limit):
    set_max_tool_calls(limit)
    reset_tool_call_count()

    for _ in range(limit):
        _check_and_increment_tool_call_count()

    with pytest.raises(ToolCallLimitExceeded) as exc_info:
        _check_and_increment_tool_call_count()

    assert exc_info.value.current_count == limit
    assert exc_info.value.max_calls == limit


def test_counter_resets_between_queries(setup_limit):
    reset_tool_call_count()
    _check_and_increment_tool_call_count()
    _check_and_increment_tool_call_count()
    assert get_tool_call_count() == 2

    reset_tool_call_count()
    assert get_tool_call_count() == 0
    _check_and_increment_tool_call_count()
    assert get_tool_call_count() == 1


@pytest.mark.parametrize(
    "initial_limit,new_limit",
    [(3, 5), (2, 3)],
)
def test_set_max_tool_calls(reset_counter, initial_limit, new_limit):
    set_max_tool_calls(initial_limit)
    reset_tool_call_count()

    for _ in range(initial_limit):
        _check_and_increment_tool_call_count()

    with pytest.raises(ToolCallLimitExceeded):
        _check_and_increment_tool_call_count()

    set_max_tool_calls(new_limit)
    reset_tool_call_count()

    for _ in range(new_limit):
        _check_and_increment_tool_call_count()

    with pytest.raises(ToolCallLimitExceeded):
        _check_and_increment_tool_call_count()
