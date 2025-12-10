# Cypher Query Agent class for graph database queries
"""Main agent class that executes Cypher queries"""

import json
import logging
from typing import Any, List

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.messages import FunctionToolCallEvent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config import DEFAULT_MAX_TOKENS
from config.instructions import InstructionsConfig, InstructionType
from cypher_agent.config import CypherAgentConfig
from cypher_agent.models import (
    CypherAgentResult,
    CypherAnswer,
    TokenUsage,
)
from cypher_agent.tools import (
    execute_cypher_query,
    get_neo4j_schema,
    initialize_neo4j_driver,
)
from monitoring.agent_logging import log_agent_run_async

logger = logging.getLogger(__name__)

# Store tool calls for evaluation
_tool_calls: List[dict] = []


async def track_tool_calls(ctx: Any, event: Any) -> None:
    """Event handler to track all tool calls"""
    global _tool_calls

    # Handle nested async streams
    if hasattr(event, "__aiter__"):
        async for sub in event:
            await track_tool_calls(ctx, sub)
        return

    # Track function tool calls
    if isinstance(event, FunctionToolCallEvent):
        tool_call = {
            "tool_name": event.part.tool_name,
            "args": event.part.args,
        }
        _tool_calls.append(tool_call)
        tool_num = len(_tool_calls)

        # Parse args to extract query for display
        try:
            args_dict = (
                json.loads(event.part.args)
                if isinstance(event.part.args, str)
                else event.part.args
            )
            query = (
                args_dict.get("query", "N/A")[:50]
                if isinstance(args_dict, dict)
                else str(event.part.args)[:50]
            )
        except (json.JSONDecodeError, AttributeError, TypeError):
            query = str(event.part.args)[:50] if event.part.args else "N/A"

        print(
            f"🔍 Tool call #{tool_num}: {event.part.tool_name} with query: {query}..."
        )
        logger.info(
            f"Tool Call #{tool_num}: {event.part.tool_name} with args: {event.part.args}"
        )


class CypherQueryAgent:
    """Cypher Query Agent that executes graph database queries"""

    def __init__(self, config: CypherAgentConfig):
        self.config = config
        self.agent = None
        self.driver = None
        self.schema = None

    def initialize(self) -> None:
        """Initialize Neo4j connection, get schema, and create agent"""
        # Connect to Neo4j
        logger.info("Connecting to Neo4j...")
        initialize_neo4j_driver(
            uri=self.config.neo4j_uri,
            user=self.config.neo4j_user,
            password=self.config.neo4j_password,
        )

        # Get schema and cache it
        logger.info("Retrieving Neo4j schema...")
        self.schema = self._get_schema()
        logger.info("Neo4j schema retrieved successfully")

        # Get base instructions and inject schema
        base_instructions = InstructionsConfig.INSTRUCTIONS[
            InstructionType.CYPHER_QUERY_AGENT
        ]
        instructions = self._inject_schema_into_instructions(
            base_instructions, self.schema
        )

        # Create OpenAI model
        model = OpenAIChatModel(
            model_name=self.config.openai_model,
            provider=OpenAIProvider(),
        )
        logger.info(f"Using OpenAI model: {self.config.openai_model}")

        # Create agent
        self.agent = Agent(
            name="cypher_query_agent",
            model=model,
            tools=[execute_cypher_query],
            instructions=instructions,
            output_type=CypherAnswer,
            model_settings=ModelSettings(max_tokens=DEFAULT_MAX_TOKENS),
        )

        logger.info("Cypher Query Agent initialized successfully")

    def _get_schema(self) -> str:
        """Retrieve and format Neo4j schema"""
        return get_neo4j_schema()

    def _inject_schema_into_instructions(self, instructions: str, schema: str) -> str:
        """Inject schema into instructions template"""
        # Replace {schema} placeholder with actual schema
        if "{schema}" in instructions:
            return instructions.replace("{schema}", schema)
        else:
            logger.warning(
                "No {schema} placeholder found in instructions. Appending schema."
            )
            return instructions + f"\n\n{schema}"

    def _reset_tool_calls(self) -> None:
        """Reset tool calls tracking (called at start of each query)"""
        global _tool_calls
        _tool_calls = []
        logger.info("Tool calls tracking reset")

    def _extract_token_usage(self, result: Any) -> TokenUsage:
        """Extract token usage from result, with fallback to zero if unavailable."""
        if result is None:
            return TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)

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

    def _extract_sources_from_result(self, result: Any) -> list[str]:
        """Extract source node IDs from result output if available."""
        if result is None:
            return []

        try:
            output = result.output
            if isinstance(output, CypherAnswer) and output.sources_used:
                logger.info(
                    f"Extracted {len(output.sources_used)} sources from result output"
                )
                return output.sources_used
        except (AttributeError, Exception) as source_error:
            logger.debug(f"Could not extract sources from result: {source_error}.")

        return []

    async def query(self, question: str) -> CypherAgentResult:
        """
        Run agent query and return result with answer and tool calls

        Args:
            question: User question to answer

        Returns:
            CypherAgentResult - Contains answer and tool calls
        """
        self._reset_tool_calls()

        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        logger.info(f"Running Cypher Query Agent query: {question[:100]}...")
        print(
            "🤖 Cypher Query Agent is processing your question (this may take 30-60 seconds)..."
        )

        # Run agent with event tracking
        result = None
        try:
            result = await self.agent.run(
                question,
                event_stream_handler=track_tool_calls,
            )
            token_usage = self._extract_token_usage(result)

            global _tool_calls
            logger.info(f"Agent completed query. Tool calls: {len(_tool_calls)}")
            print(
                f"✅ Cypher Query Agent completed query. Made {len(_tool_calls)} tool calls."
            )

            # Log agent run asynchronously
            try:
                log_agent_run_async(self.agent, result, question)
            except Exception as e:
                logger.warning(f"Failed to start background logging task: {e}")

            return CypherAgentResult(
                answer=result.output,
                tool_calls=_tool_calls.copy(),
                token_usage=token_usage,
            )

        except Exception as e:
            logger.error(f"Error during Cypher Query Agent execution: {e}")
            raise
