"""Configuration for Orchestrator Agent"""

from dataclasses import dataclass

from config import (
    DEFAULT_RAG_MODEL,
    OPENAI_RAG_MODEL,
    InstructionType,
)


@dataclass
class OrchestratorConfig:
    """Configuration for Orchestrator system"""

    openai_model: str = OPENAI_RAG_MODEL  # OpenAI model name (e.g., "gpt-4o-mini")
    instruction_type: InstructionType = InstructionType.ORCHESTRATOR_AGENT
    rag_agent_config: dict | None = None  # Configuration to pass to RAG Agent
    cypher_agent_config: dict | None = (
        None  # Configuration to pass to Cypher Query Agent
    )
