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
    openai_model: str = OPENAI_RAG_MODEL
    instruction_type: InstructionType = InstructionType.CYPHER_QUERY_AGENT
    neo4j_uri: str = NEO4J_URI
    neo4j_user: str = NEO4J_USER
    neo4j_password: str = NEO4J_PASSWORD
    max_tool_calls: int = 5
    max_tokens: int = CYPHER_AGENT_MAX_TOKENS
    max_schema_size: int = 5000
    max_query_results: int = 100
    max_tool_result_size: int = 50000  # Maximum size of tool call result in characters (prevents token overflow)
