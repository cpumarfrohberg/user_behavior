"""Orchestrator Agent for intelligent query routing"""

import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config import DEFAULT_MAX_TOKENS, InstructionsConfig, InstructionType
from orchestrator.config import OrchestratorConfig
from orchestrator.models import OrchestratorAnswer
from orchestrator.tools import call_cypher_query_agent, call_rag_agent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Orchestrator Agent that intelligently routes queries to appropriate agents"""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.agent = None

    def initialize(self) -> None:
        """Initialize orchestrator agent with tools"""
        logger.info("Initializing Orchestrator Agent...")

        # Get instructions from config
        instructions = InstructionsConfig.INSTRUCTIONS[
            InstructionType.ORCHESTRATOR_AGENT
        ]

        # Initialize OpenAI model
        model = OpenAIChatModel(
            model_name=self.config.openai_model,
            provider=OpenAIProvider(),
        )
        logger.info(f"Using OpenAI model: {self.config.openai_model}")

        # Create agent with tools to call other agents
        from pydantic_ai import ModelSettings

        self.agent = Agent(
            name="orchestrator_agent",
            model=model,
            tools=[call_rag_agent, call_cypher_query_agent],
            instructions=instructions,
            output_type=OrchestratorAnswer,
            model_settings=ModelSettings(max_tokens=DEFAULT_MAX_TOKENS),
        )

        logger.info("Orchestrator Agent initialized successfully")

    async def query(self, question: str) -> OrchestratorAnswer:
        """
        Run orchestrator query and return synthesized answer

        Args:
            question: User question to answer

        Returns:
            OrchestratorAnswer - Synthesized answer from appropriate agent(s)
        """
        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        logger.info(f"Running orchestrator query: {question[:100]}...")
        print(
            "🎯 Orchestrator is analyzing your question and routing to the best agent..."
        )

        # Run agent - it will intelligently route to appropriate agent(s)
        try:
            result = await self.agent.run(question)
        except Exception as e:
            logger.error(f"Error during orchestrator execution: {e}")
            raise

        logger.info(
            f"Orchestrator completed query. Agents used: {result.output.agents_used}"
        )
        print(
            f"✅ Orchestrator completed. Used agents: {', '.join(result.output.agents_used)}"
        )

        return result.output
