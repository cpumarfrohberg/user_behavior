"""Configuration for Orchestrator Agent"""

from dataclasses import dataclass

from config import (
    ENABLE_ORCHESTRATOR_JUDGE,
    OPENAI_RAG_MODEL,
    InstructionType,
)


@dataclass
class OrchestratorConfig:
    """Configuration for Orchestrator system"""

    openai_model: str = OPENAI_RAG_MODEL  # OpenAI model name (e.g., "gpt-4o-mini")
    instruction_type: InstructionType = InstructionType.ORCHESTRATOR_AGENT
    mongodb_agent_config: dict | None = None  # Configuration to pass to MongoDB Agent
    cypher_agent_config: dict | None = (
        None  # Configuration to pass to Cypher Query Agent
    )
    enable_judge_evaluation: bool = (
        ENABLE_ORCHESTRATOR_JUDGE  # Enable LLM judge evaluation of synthesized answers
    )
