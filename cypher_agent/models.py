# Pydantic models for Cypher Query Agent
"""Pydantic models for Cypher Query Agent system"""

from pydantic import BaseModel, Field

from mongodb_agent.models import TokenUsage

# Constants for validation bounds
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


class CypherAnswer(BaseModel):
    """Structured response from Cypher Query Agent"""

    answer: str = Field(..., description="The answer to the user's question")
    confidence: float = Field(
        ...,
        ge=MIN_CONFIDENCE,
        le=MAX_CONFIDENCE,
        description=f"Confidence in the answer ({MIN_CONFIDENCE} to {MAX_CONFIDENCE})",
    )
    sources_used: list[str] = Field(
        ..., description="List of source node IDs used to generate the answer"
    )
    reasoning: str | None = Field(
        None, description="Brief explanation of the reasoning behind the answer"
    )
    query_used: str = Field(
        ..., description="The Cypher query that was executed to generate this answer"
    )


class CypherAgentResult(BaseModel):
    """Result from Cypher Query Agent query"""

    answer: CypherAnswer = Field(..., description="The answer from the agent")
    tool_calls: list[dict] = Field(
        ..., description="List of tool calls made during the query"
    )
    token_usage: TokenUsage = Field(
        ..., description="Token usage information from the agent"
    )
