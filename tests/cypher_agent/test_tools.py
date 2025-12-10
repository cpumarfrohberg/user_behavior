"""Tests for Cypher Query Agent tools"""

from unittest.mock import MagicMock, patch

import pytest

from cypher_agent.tools import (
    execute_cypher_query,
    get_neo4j_driver,
    get_neo4j_schema,
    initialize_neo4j_driver,
    validate_cypher_query,
)


class TestValidateCypherQuery:
    """Test query validation function"""

    def test_valid_read_query(self):
        """Test that valid read-only queries pass validation"""
        query = "MATCH (n:User) RETURN n LIMIT 10"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is True
        assert error is None

    def test_query_with_where_clause(self):
        """Test query with WHERE clause"""
        query = "MATCH (q:Question)-[:HAS_TAG]->(t:Tag) WHERE t.name = 'user-behavior' RETURN q"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is True
        assert error is None

    def test_query_with_aggregation(self):
        """Test query with WITH aggregation"""
        query = "MATCH (u:User)-[:ASKED]->(q:Question) WITH u, count(q) as question_count RETURN u, question_count"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is True
        assert error is None

    def test_forbidden_create_operation(self):
        """Test that CREATE operations are rejected"""
        query = "CREATE (n:User {name: 'test'}) RETURN n"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "CREATE" in error.upper()
        assert "forbidden" in error.lower()

    def test_forbidden_delete_operation(self):
        """Test that DELETE operations are rejected"""
        query = "MATCH (n:User) DELETE n"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "DELETE" in error.upper()

    def test_forbidden_set_operation(self):
        """Test that SET operations are rejected"""
        query = "MATCH (n:User) SET n.name = 'test' RETURN n"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "SET" in error.upper()

    def test_forbidden_merge_operation(self):
        """Test that MERGE operations are rejected"""
        query = "MERGE (n:User {id: 1}) RETURN n"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "MERGE" in error.upper()

    def test_forbidden_group_by(self):
        """Test that GROUP BY is rejected"""
        query = "MATCH (u:User)-[:ASKED]->(q:Question) RETURN u, count(q) GROUP BY u"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "GROUP BY" in error.upper()

    def test_empty_query(self):
        """Test that empty queries are rejected"""
        is_valid, error = validate_cypher_query("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_whitespace_only_query(self):
        """Test that whitespace-only queries are rejected"""
        is_valid, error = validate_cypher_query("   \n\t  ")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_unbalanced_parentheses(self):
        """Test detection of unbalanced parentheses"""
        query = "MATCH (n:User RETURN n"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "parentheses" in error.lower()

    def test_unbalanced_brackets(self):
        """Test detection of unbalanced brackets"""
        query = "MATCH (n:User)-[:ASKED->(q:Question) RETURN n"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "brackets" in error.lower()

    def test_unbalanced_braces(self):
        """Test detection of unbalanced braces"""
        query = "MATCH (n:User {name: 'test') RETURN n"
        is_valid, error = validate_cypher_query(query)
        assert is_valid is False
        assert "braces" in error.lower()


class TestNeo4jDriver:
    """Test Neo4j driver initialization"""

    @patch("cypher_agent.tools.GraphDatabase")
    def test_initialize_neo4j_driver(self, mock_graph_db, mock_neo4j_driver):
        """Test driver initialization"""
        mock_graph_db.driver.return_value = mock_neo4j_driver

        initialize_neo4j_driver("bolt://localhost:7687", "neo4j", "password")

        mock_graph_db.driver.assert_called_once_with(
            "bolt://localhost:7687", auth=("neo4j", "password")
        )
        mock_neo4j_driver.verify_connectivity.assert_called_once()

    @patch("cypher_agent.tools._neo4j_driver", None)
    def test_get_neo4j_driver_not_initialized(self):
        """Test that getting driver before initialization raises error"""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_neo4j_driver()

    def test_get_neo4j_driver_initialized(self, mock_neo4j_driver):
        """Test getting initialized driver"""
        with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
            driver = get_neo4j_driver()
            assert driver == mock_neo4j_driver


class TestGetNeo4jSchema:
    """Test schema retrieval"""

    def test_get_schema_success(self, mock_neo4j_driver, mock_neo4j_schema):
        """Test successful schema retrieval"""
        # Mock the session run to return schema records
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

        assert schema is not None
        assert len(schema) > 0
        assert "NEO4J SCHEMA" in schema
        session.run.assert_called_once_with("CALL db.schema.nodeTypeProperties()")

    def test_get_schema_connection_error(self, mock_neo4j_driver):
        """Test schema retrieval with connection error"""
        session = mock_neo4j_driver.session.return_value.__enter__.return_value
        session.run.side_effect = Exception("Connection failed")

        with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
            schema = get_neo4j_schema()

        # Should return fallback schema
        assert schema is not None
        assert "Schema retrieval failed" in schema


class TestExecuteCypherQuery:
    """Test query execution"""

    def test_execute_valid_query(self, mock_neo4j_driver):
        """Test executing a valid query"""
        session = mock_neo4j_driver.session.return_value.__enter__.return_value

        # Mock Neo4j record
        mock_record = MagicMock()
        mock_record.keys.return_value = ["user_id", "display_name"]
        mock_record.__getitem__.side_effect = lambda key: {
            "user_id": 1,
            "display_name": "TestUser",
        }[key]

        session.run.return_value = [mock_record]

        query = "MATCH (u:User) RETURN u.user_id, u.display_name LIMIT 1"

        with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
            result = execute_cypher_query(query)

        assert result["error"] is None
        assert len(result["results"]) == 1
        assert result["query"] == query
        # Note: execute_cypher_query converts values to strings if they have __str__
        assert (
            result["results"][0]["user_id"] == "1"
        )  # Converted to string by the function
        assert result["results"][0]["display_name"] == "TestUser"

    def test_execute_invalid_query(self, mock_neo4j_driver):
        """Test executing an invalid query (validation fails)"""
        query = "CREATE (n:User) RETURN n"

        with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
            result = execute_cypher_query(query)

        assert result["error"] is not None
        assert (
            "forbidden" in result["error"].lower()
            or "CREATE" in result["error"].upper()
        )
        assert result["results"] == []
        assert result["query"] == query

    def test_execute_query_syntax_error(self, mock_neo4j_driver):
        """Test executing query with syntax error from Neo4j"""
        from neo4j.exceptions import CypherSyntaxError

        session = mock_neo4j_driver.session.return_value.__enter__.return_value
        session.run.side_effect = CypherSyntaxError("Invalid syntax: unexpected token")

        # Use a query that passes validation but fails at Neo4j
        # This query has balanced parentheses and no forbidden keywords,
        # but has invalid Cypher syntax that Neo4j will catch
        query = "MATCH (n:User) RETURN n INVALID_KEYWORD"  # Invalid Cypher syntax

        with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
            result = execute_cypher_query(query)

        assert result["error"] is not None
        assert "syntax" in result["error"].lower()
        assert result["results"] == []

    def test_execute_query_service_unavailable(self, mock_neo4j_driver):
        """Test executing query when Neo4j service is unavailable"""
        from neo4j.exceptions import ServiceUnavailable

        session = mock_neo4j_driver.session.return_value.__enter__.return_value
        session.run.side_effect = ServiceUnavailable("Service unavailable")

        query = "MATCH (n:User) RETURN n LIMIT 10"

        with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
            result = execute_cypher_query(query)

        assert result["error"] is not None
        assert "unavailable" in result["error"].lower()
        assert result["results"] == []

    def test_execute_query_empty_results(self, mock_neo4j_driver):
        """Test executing query that returns no results"""
        session = mock_neo4j_driver.session.return_value.__enter__.return_value
        session.run.return_value = []  # No results

        query = "MATCH (n:User) WHERE n.user_id = 99999 RETURN n"

        with patch("cypher_agent.tools._neo4j_driver", mock_neo4j_driver):
            result = execute_cypher_query(query)

        assert result["error"] is None
        assert result["results"] == []
        assert result["query"] == query
