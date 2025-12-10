"""Cypher Query Agent configuration dataclass"""

from dataclasses import dataclass

from config import (
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
