"""Orchestrator Agent for intelligent query routing"""

import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config import DEFAULT_MAX_TOKENS, InstructionsConfig, InstructionType
from mongodb_agent.models import TokenUsage
from orchestrator.config import OrchestratorConfig
from orchestrator.models import OrchestratorAgentResult, OrchestratorAnswer
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

    def _extract_token_usage(self, result: Any) -> TokenUsage:
        """Extract token usage from result, with fallback to zero if unavailable."""
        try:
            usage_obj = result.usage()
            return TokenUsage(
                input_tokens=usage_obj.input_tokens,
                output_tokens=usage_obj.output_tokens,
                total_tokens=usage_obj.input_tokens + usage_obj.output_tokens,
            )
        except (AttributeError, Exception) as usage_error:
            logger.warning(
                f"Could not extract token usage from result: {usage_error}. "
                f"Using fallback token usage."
            )
            return TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)

    async def query(self, question: str) -> OrchestratorAgentResult:
        """
        Run orchestrator query and return result with answer and token usage

        Args:
            question: User question to answer

        Returns:
            OrchestratorAgentResult - Contains answer and token usage
        """
        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        logger.info(f"Running orchestrator query: {question[:100]}...")
        print(
            "🎯 Orchestrator is analyzing your question and routing to the best agent..."
        )

        # Run agent - it will intelligently route to appropriate agent(s)
        result = None
        try:
            result = await self.agent.run(question)
        except Exception as e:
            logger.error(f"Error during orchestrator execution: {e}")
            raise

        # Extract token usage
        token_usage = self._extract_token_usage(result)

        logger.info(
            f"Orchestrator completed query. Agents used: {result.output.agents_used}, "
            f"Token usage: {token_usage.total_tokens}"
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

        return OrchestratorAgentResult(
            answer=result.output,
            token_usage=token_usage,
        )
