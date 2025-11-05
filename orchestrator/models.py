"""Pydantic models for Orchestrator Agent"""

from pydantic import BaseModel, Field


class OrchestratorAnswer(BaseModel):
    """Structured response from Orchestrator system"""

    answer: str = Field(
        ..., description="The synthesized answer to the user's question"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the answer (0.0 to 1.0)"
    )
    agents_used: list[str] = Field(
        ...,
        description="List of agents that were called (e.g., ['rag_agent', 'cypher_query_agent'])",
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why these agents were chosen and how results were combined",
    )
    sources_used: list[str] | None = Field(
        None, description="List of sources used (from RAG agent if applicable)"
    )
