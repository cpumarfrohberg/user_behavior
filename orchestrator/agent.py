"""Orchestrator Agent for intelligent query routing"""

import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config import DEFAULT_MAX_TOKENS, InstructionsConfig, InstructionType
from orchestrator.config import OrchestratorConfig
from orchestrator.models import OrchestratorAnswer
from orchestrator.tools import (
    call_both_agents_parallel,
    call_cypher_query_agent,
    call_mongodb_agent,
)

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
            tools=[
                call_both_agents_parallel,  # Parallel execution (preferred when both needed)
                call_mongodb_agent,
                call_cypher_query_agent,
            ],
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

        # Judge evaluation (optional)
        if self.config.enable_judge_evaluation:
            try:
                from evals.judge import evaluate_orchestrator_answer

                # Extract tool calls from result if available
                tool_calls = []
                # Note: pydantic-ai doesn't expose tool calls directly in result
                # We'd need to track them via event handlers if needed
                # For now, we'll pass None

                judge_result = await evaluate_orchestrator_answer(
                    question=question,
                    answer=result.output,
                    tool_calls=tool_calls,
                )
                logger.info(
                    f"Judge evaluation: overall_score={judge_result.evaluation.overall_score:.2f}, "
                    f"accuracy={judge_result.evaluation.accuracy:.2f}, "
                    f"completeness={judge_result.evaluation.completeness:.2f}, "
                    f"relevance={judge_result.evaluation.relevance:.2f}"
                )
            except Exception as e:
                logger.warning(f"Judge evaluation failed: {e}")

        # Log agent run to database (non-blocking background task)
        try:
            from monitoring.agent_logging import log_agent_run_async

            log_agent_run_async(self.agent, result, question)
        except Exception as e:
            logger.warning(f"Failed to start background logging task: {e}")

        return result.output
