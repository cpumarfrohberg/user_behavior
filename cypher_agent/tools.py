# Tool functions for Cypher Query Agent
"""Neo4j query execution tool function that agent can call"""

import logging
import re
import threading
from typing import Any

import neo4j
from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError, ServiceUnavailable

from mongodb_agent.tools import ToolCallLimitExceeded

logger = logging.getLogger(__name__)

# Tool call limit constants
DEFAULT_TOOL_CALL_COUNT = 0
DEFAULT_MAX_TOOL_CALLS = 5

# Global Neo4j driver instance
_neo4j_driver: neo4j.Driver | None = None

# Global state for tool call counting
_tool_call_count = DEFAULT_TOOL_CALL_COUNT
_initial_max_tool_calls = DEFAULT_MAX_TOOL_CALLS
_extended_max_tool_calls = DEFAULT_MAX_TOOL_CALLS
_current_max_tool_calls = DEFAULT_MAX_TOOL_CALLS
_enable_adaptive_limit = False
_counter_lock = threading.Lock()


def set_max_tool_calls(max_calls: int) -> None:
    """Set the maximum number of tool calls allowed."""
    global _initial_max_tool_calls, _current_max_tool_calls
    with _counter_lock:
        _initial_max_tool_calls = max_calls
        _current_max_tool_calls = max_calls


def set_adaptive_limit_config(
    initial_limit: int, extended_limit: int, enabled: bool
) -> None:
    """Configure adaptive limit settings."""
    global \
        _initial_max_tool_calls, \
        _extended_max_tool_calls, \
        _current_max_tool_calls, \
        _enable_adaptive_limit
    with _counter_lock:
        _initial_max_tool_calls = initial_limit
        _extended_max_tool_calls = extended_limit
        _current_max_tool_calls = initial_limit
        _enable_adaptive_limit = enabled


def reset_tool_call_count() -> None:
    """Reset the tool call counter and limit (called at start of each query)."""
    global _tool_call_count, _current_max_tool_calls
    with _counter_lock:
        _tool_call_count = DEFAULT_TOOL_CALL_COUNT
        _current_max_tool_calls = _initial_max_tool_calls


def get_tool_call_count() -> int:
    """Get the current tool call count."""
    global _tool_call_count
    with _counter_lock:
        return _tool_call_count


def _check_and_increment_tool_call_count() -> int:
    """Check limit before incrementing, raise exception if limit reached."""
    global _tool_call_count, _current_max_tool_calls

    with _counter_lock:
        if _tool_call_count >= _current_max_tool_calls:
            logger.warning(
                f"Tool call limit reached: {_tool_call_count} >= {_current_max_tool_calls}. "
                f"Blocking call before it starts."
            )
            raise ToolCallLimitExceeded(_tool_call_count, _current_max_tool_calls)

        _tool_call_count += 1
        logger.info(
            f"✅ Tool call #{_tool_call_count} of {_current_max_tool_calls} allowed"
        )
        return _tool_call_count


# Forbidden write operations
FORBIDDEN_KEYWORDS = ["CREATE", "DELETE", "SET", "REMOVE", "MERGE"]
FORBIDDEN_PATTERNS = [
    r"\bCREATE\b",
    r"\bDELETE\b",
    r"\bSET\b",
    r"\bREMOVE\b",
    r"\bMERGE\b",
]

# Allowed read-only keywords
ALLOWED_KEYWORDS = [
    "MATCH",
    "RETURN",
    "WHERE",
    "WITH",
    "OPTIONAL MATCH",
    "ORDER BY",
    "LIMIT",
    "DISTINCT",
    "COUNT",
    "SUM",
    "AVG",
    "MAX",
    "MIN",
    "COLLECT",
]


def initialize_neo4j_driver(uri: str, user: str, password: str) -> None:
    """
    Initialize Neo4j driver connection.

    Args:
        uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
        user: Neo4j username
        password: Neo4j password
    """
    global _neo4j_driver

    if _neo4j_driver is None:
        logger.info(f"Connecting to Neo4j at {uri}...")
        try:
            _neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
            # Verify connection
            _neo4j_driver.verify_connectivity()
            logger.info("Neo4j driver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            raise RuntimeError(f"Neo4j connection failed: {str(e)}") from e
    else:
        logger.info("Neo4j driver already initialized")


def get_neo4j_driver() -> neo4j.Driver:
    """Get the global Neo4j driver instance."""
    global _neo4j_driver
    if _neo4j_driver is None:
        raise RuntimeError(
            "Neo4j driver not initialized. Call initialize_neo4j_driver first."
        )
    return _neo4j_driver


def get_neo4j_schema() -> str:
    """
    Retrieve Neo4j schema and format as text for prompt injection.

    Uses db.schema.nodeTypeProperties() to get comprehensive schema information
    including node labels, relationship types, and their properties.

    Returns:
        Formatted schema string with node labels, relationship types, and properties
    """
    driver = get_neo4j_driver()

    try:
        with driver.session(database="neo4j") as session:
            # Query schema using db.schema.nodeTypeProperties()
            result = session.run("CALL db.schema.nodeTypeProperties()")

            # Collect schema information
            node_properties = {}
            rel_properties = {}
            node_labels = set()
            rel_types = set()

            for record in result:
                node_labels.add(
                    record.get("nodeLabels", [None])[0]
                    if record.get("nodeLabels")
                    else None
                )
                rel_types.add(record.get("relType"))

                properties = record.get("propertyName")
                property_types = record.get("propertyTypes", [])

                if record.get("nodeLabels"):
                    label = record.get("nodeLabels")[0]
                    if label:
                        if label not in node_properties:
                            node_properties[label] = []
                        if properties:
                            node_properties[label].append(
                                {"name": properties, "types": property_types}
                            )

                if record.get("relType"):
                    rel_type = record.get("relType")
                    if rel_type not in rel_properties:
                        rel_properties[rel_type] = []
                    if properties:
                        rel_properties[rel_type].append(
                            {"name": properties, "types": property_types}
                        )

            # Format schema as text
            schema_lines = ["NEO4J SCHEMA", "=" * 50, ""]

            # Node Labels and Properties
            schema_lines.append("NODE LABELS:")
            for label in sorted(node_labels):
                if label:
                    schema_lines.append(f"  - {label}")
                    if label in node_properties:
                        props = node_properties[label]
                        if props:
                            schema_lines.append("    Properties:")
                            for prop in props:
                                prop_types = (
                                    ", ".join(prop["types"])
                                    if prop["types"]
                                    else "unknown"
                                )
                                schema_lines.append(
                                    f"      - {prop['name']}: {prop_types}"
                                )

            schema_lines.append("")

            # Relationship Types and Properties
            schema_lines.append("RELATIONSHIP TYPES:")
            for rel_type in sorted(rel_types):
                if rel_type:
                    schema_lines.append(f"  - {rel_type}")
                    if rel_type in rel_properties:
                        props = rel_properties[rel_type]
                        if props:
                            schema_lines.append("    Properties:")
                            for prop in props:
                                prop_types = (
                                    ", ".join(prop["types"])
                                    if prop["types"]
                                    else "unknown"
                                )
                                schema_lines.append(
                                    f"      - {prop['name']}: {prop_types}"
                                )

            schema_text = "\n".join(schema_lines)
            logger.info("Neo4j schema retrieved successfully")
            return schema_text

    except Exception as e:
        logger.error(f"Error retrieving Neo4j schema: {e}")
        # Return a basic schema if query fails
        return (
            "NEO4J SCHEMA\n"
            + "=" * 50
            + "\n\nSchema retrieval failed. Use standard StackExchange node labels and relationship types."
        )


def validate_cypher_query(query: str) -> tuple[bool, str | None]:
    """
    Validate Cypher query before execution.

    Checks for:
    1. Write operations (CREATE, DELETE, SET, REMOVE, MERGE)
    2. Basic syntax validation (balanced parentheses, brackets)
    3. GROUP BY usage (should use WITH aggregation instead)

    Args:
        query: Cypher query string to validate

    Returns:
        Tuple of (is_valid, error_message)
        - If valid: (True, None)
        - If invalid: (False, error_message)
    """
    if not query or not query.strip():
        return False, "Query is empty"

    query_upper = query.upper()

    # Check for write operations
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in query_upper:
            # Check if it's actually a write operation (not in comments or strings)
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, query_upper):
                return (
                    False,
                    f"Forbidden write operation detected: {keyword}. Only read-only queries are allowed.",
                )

    # Check for GROUP BY (should use WITH aggregation instead)
    if re.search(r"\bGROUP\s+BY\b", query_upper):
        return (
            False,
            "GROUP BY is not allowed. Use WITH aggregation instead (e.g., WITH ... count(...) as ...).",
        )

    # Basic syntax validation - check balanced parentheses
    paren_count = query.count("(") - query.count(")")
    if paren_count != 0:
        return (
            False,
            f"Unbalanced parentheses: {abs(paren_count)} extra {'opening' if paren_count > 0 else 'closing'} parenthesis",
        )

    # Check balanced brackets
    bracket_count = query.count("[") - query.count("]")
    if bracket_count != 0:
        return (
            False,
            f"Unbalanced brackets: {abs(bracket_count)} extra {'opening' if bracket_count > 0 else 'closing'} bracket",
        )

    # Check balanced braces
    brace_count = query.count("{") - query.count("}")
    if brace_count != 0:
        return (
            False,
            f"Unbalanced braces: {abs(brace_count)} extra {'opening' if brace_count > 0 else 'closing'} brace",
        )

    return True, None


def execute_cypher_query(query: str) -> dict[str, Any]:
    """
    Execute Cypher query on Neo4j and return results.

    ⚠️ IMPORTANT: This tool executes read-only queries only. Write operations are forbidden.
    ⚠️ IMPORTANT LIMIT: You have a maximum of 5 tool calls per query. After 5 calls,
    this tool will raise ToolCallLimitExceeded and you MUST stop and synthesize your answer.
    Most questions can be answered with just 1-2 queries. Be decisive and stop early.

    Args:
        query: Cypher query string to execute

    Returns:
        Dictionary with format:
        {
            "results": [...],  # List of result records
            "query": query,    # The executed query
            "error": None or str  # Error message if execution failed
        }

    Raises:
        RuntimeError: If Neo4j driver is not initialized or query validation fails
        ToolCallLimitExceeded: If you have exceeded the maximum of 5 tool calls.
    """
    global _tool_call_count, _current_max_tool_calls, _initial_max_tool_calls

    driver = get_neo4j_driver()

    # Check for suspicious counter state (shouldn't happen, but safety check)
    with _counter_lock:
        if _tool_call_count > _current_max_tool_calls:
            logger.warning(
                f"Counter state suspicious: {_tool_call_count} > {_current_max_tool_calls}. "
                f"This suggests counter wasn't reset between queries. Resetting now."
            )
            _tool_call_count = DEFAULT_TOOL_CALL_COUNT
            _current_max_tool_calls = _initial_max_tool_calls

    # Check and increment tool call count (raises exception if limit exceeded)
    _check_and_increment_tool_call_count()

    # Validate query before execution
    is_valid, error_message = validate_cypher_query(query)
    if not is_valid:
        logger.warning(f"Query validation failed: {error_message}")
        return {
            "results": [],
            "query": query,
            "error": error_message,
        }

    try:
        logger.info(f"Executing Cypher query: {query[:100]}...")

        with driver.session(database="neo4j") as session:
            result = session.run(query)

            # Convert results to list of dictionaries
            records = []
            for record in result:
                # Convert Neo4j record to dict
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    # Convert Neo4j types to Python types
                    if isinstance(value, list):
                        record_dict[key] = [
                            str(v) if hasattr(v, "__str__") else v for v in value
                        ]
                    elif hasattr(value, "__str__"):
                        # Handle Neo4j node/relationship objects
                        if hasattr(value, "id"):
                            record_dict[key] = {
                                "id": value.id,
                                "labels": list(value.labels)
                                if hasattr(value, "labels")
                                else [],
                                "properties": dict(value.items())
                                if hasattr(value, "items")
                                else {},
                            }
                        else:
                            record_dict[key] = str(value)
                    else:
                        record_dict[key] = value

                records.append(record_dict)

            logger.info(
                f"Query executed successfully. Returned {len(records)} records."
            )

            return {
                "results": records,
                "query": query,
                "error": None,
            }

    except CypherSyntaxError as e:
        error_msg = f"Cypher syntax error: {str(e)}"
        logger.error(error_msg)
        return {
            "results": [],
            "query": query,
            "error": error_msg,
        }
    except ServiceUnavailable as e:
        error_msg = f"Neo4j service unavailable: {str(e)}"
        logger.error(error_msg)
        return {
            "results": [],
            "query": query,
            "error": error_msg,
        }
    except Exception as e:
        error_msg = f"Query execution error: {str(e)}"
        logger.error(error_msg)
        return {
            "results": [],
            "query": query,
            "error": error_msg,
        }
