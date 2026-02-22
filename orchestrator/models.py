"""Pydantic models for Orchestrator Agent"""

from typing import Literal

from pydantic import BaseModel, Field

from mongodb_agent.models import TokenUsage


class RoutingLog(BaseModel):
    """Structured routing log for each orchestrator decision."""

    route: Literal["RAG", "CYPHER", "BOTH"] = Field(
        ..., description="Which agent(s) were chosen"
    )
    queries: dict[str, str] = Field(
        default_factory=dict,
        description="Question(s) passed to tools; e.g. {'rag': '...', 'cypher': '...'} or single key. For single-agent calls, use one key; for BOTH use both.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags used for RAG (if any); usually empty at orchestrator level",
    )
    tool_called: Literal[
        "call_mongodb_agent", "call_cypher_query_agent", "call_both_agents_parallel"
    ] = Field(..., description="The tool that was invoked")
    reason: str = Field(..., description="One-line rationale for routing (≤ 12 words)")
    notes: str = Field(
        default="",
        description="Error/fallback notes or empty",
    )


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
        description="List of agents that were called (e.g., ['mongodb_agent', 'cypher_query_agent'])",
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why these agents were chosen and how results were combined",
    )
    sources_used: list[str] | None = Field(
        None, description="List of sources used (from RAG agent if applicable)"
    )
    routing_log: RoutingLog | None = Field(
        None,
        description="Structured routing log: route, queries, tool_called, reason, notes. Must be filled for every response.",
    )


class OrchestratorAgentResult(BaseModel):
    """Result from Orchestrator agent query including token usage"""

    answer: OrchestratorAnswer = Field(
        ..., description="The answer from the orchestrator"
    )
    token_usage: TokenUsage = Field(
        ..., description="Token usage information from the orchestrator"
    )
