"""Cypher Query Agent configuration dataclass"""

from dataclasses import dataclass

from config import (
    CYPHER_AGENT_MAX_TOKENS,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    OPENAI_RAG_MODEL,
    InstructionType,
)


@dataclass
class CypherAgentConfig:
    """Configuration for Cypher Query Agent"""

    openai_model: str = OPENAI_RAG_MODEL
    instruction_type: InstructionType = InstructionType.CYPHER_QUERY_AGENT
    neo4j_uri: str = NEO4J_URI
    neo4j_user: str = NEO4J_USER
    neo4j_password: str = NEO4J_PASSWORD
    max_tool_calls: int = 5  # Maximum number of tool calls allowed per query
    max_tokens: int = CYPHER_AGENT_MAX_TOKENS  # Maximum tokens for agent responses
    max_schema_size: int = (
        5000  # Maximum schema size in characters (prevents context overflow)
    )
    max_query_results: int = 100  # Maximum number of records to return from a query
