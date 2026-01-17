# MongoDB Agent class for making repetitive tool calls
"""Main agent class that orchestrates multiple tool calls"""

import json
import logging
from typing import Any, List

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.messages import FunctionToolCallEvent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pymongo import MongoClient

from config import DEFAULT_MAX_TOKENS
from config.instructions import InstructionsConfig, InstructionType
from mongodb_agent.config import (
    LIMIT_REACHED_CONFIDENCE,
    MAX_RESET_ATTEMPTS,
    QUERY_DISPLAY_TRUNCATE_LENGTH,
    QUESTION_LOG_TRUNCATE_LENGTH,
    MongoDBConfig,
)
from mongodb_agent.models import (
    SearchAgentResult,
    SearchAnswer,
    SearchEntry,
    TokenUsage,
)
from mongodb_agent.tools import (
    ToolCallLimitExceeded,
    get_sources,
    get_tool_call_count,
    initialize_mongodb_collection,
    reset_tool_call_count,
    search_mongodb,
    set_adaptive_limit_config,
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

        # Note: Counter increment is now handled by tool function's pre-call validation
        # (see _check_and_increment_tool_call_count in tools.py)
        # This prevents double-counting and ensures thread-safe limit enforcement

        # Parse args to extract query for display
        try:
            args_dict = (
                json.loads(event.part.args)
                if isinstance(event.part.args, str)
                else event.part.args
            )
            query = (
                args_dict.get("query", "N/A")[:QUERY_DISPLAY_TRUNCATE_LENGTH]
                if isinstance(args_dict, dict)
                else str(event.part.args)[:QUERY_DISPLAY_TRUNCATE_LENGTH]
            )
        except (json.JSONDecodeError, AttributeError, TypeError):
            query = (
                str(event.part.args)[:QUERY_DISPLAY_TRUNCATE_LENGTH]
                if event.part.args
                else "N/A"
            )

        print(
            f"🔍 Tool call #{tool_num}: {event.part.tool_name} with query: {query}..."
        )
        logger.info(
            f"Tool Call #{tool_num}: {event.part.tool_name} with args: {event.part.args}"
        )


class MongoDBSearchAgent:
    """MongoDB Search Agent that makes repetitive tool calls for better retrieval"""

    def __init__(self, config: MongoDBConfig):
        self.config = config
        self.agent = None
        self.client = None
        self.db = None
        self.collection = None

    def initialize(self) -> None:
        """Initialize MongoDB connection and create agent"""
        # Connect to MongoDB
        logger.info("Connecting to MongoDB...")
        self.client = MongoClient(self.config.mongo_uri)
        self.db = self.client[self.config.database]
        self.collection = self.db[self.config.collection]

        # Create text index if it doesn't exist
        try:
            indexes = list(self.collection.list_indexes())
            has_text_index = any(
                idx.get("textIndexVersion") is not None for idx in indexes
            )

            if not has_text_index:
                logger.info("Creating text index on title and body fields...")
                self.collection.create_index([("title", "text"), ("body", "text")])
                logger.info("Text index created successfully")
            else:
                logger.info("Text index already exists")
        except Exception as e:
            logger.warning(
                f"Could not create/verify text index: {e}. "
                f"Text search may not work if index doesn't exist."
            )

        initialize_mongodb_collection(self.collection)

        set_adaptive_limit_config(
            initial_limit=self.config.initial_max_tool_calls,
            extended_limit=self.config.extended_max_tool_calls,
            enabled=self.config.enable_adaptive_limit,
        )

        instructions = InstructionsConfig.INSTRUCTIONS[InstructionType.MONGODB_AGENT]

        model = OpenAIChatModel(
            model_name=self.config.openai_model,
            provider=OpenAIProvider(),
        )
        logger.info(f"Using OpenAI model: {self.config.openai_model}")

        self.agent = Agent(
            name="mongodb_agent",
            model=model,
            tools=[search_mongodb],
            instructions=instructions,
            output_type=SearchAnswer,
            model_settings=ModelSettings(max_tokens=DEFAULT_MAX_TOKENS),
        )

        logger.info("MongoDB Agent initialized successfully")

    def _reset_and_verify_counters(self) -> None:
        """Reset tool calls and counter, verify counter is properly reset."""
        global _tool_calls
        _tool_calls = []

        reset_tool_call_count()
        # Verify counter is reset to 0
        initial_count = get_tool_call_count()
        if initial_count != 0:
            logger.error(
                f"CRITICAL: Counter not properly reset! Expected 0, got {initial_count}. "
                f"This indicates a potential race condition or counter corruption. "
                f"Resetting again..."
            )
            reset_tool_call_count()
            initial_count = get_tool_call_count()
            if initial_count != 0:
                raise RuntimeError(
                    f"Failed to reset tool call counter after {MAX_RESET_ATTEMPTS} attempts. "
                    f"Counter stuck at {initial_count}. This is a critical error."
                )
            logger.warning(
                f"Counter reset succeeded on second attempt. "
                f"This should not happen - investigate potential race conditions."
            )
        logger.info(f"✅ Tool call counter reset to {initial_count} (verified)")

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
        """Extract sources from result output if available, otherwise from tracked sources."""
        # First try to get sources from result output (if LLM finished synthesizing)
        if result is not None:
            try:
                output = result.output
                if isinstance(output, SearchAnswer) and output.sources_used:
                    logger.info(
                        f"Extracted {len(output.sources_used)} sources from result output"
                    )
                    return output.sources_used
            except (AttributeError, Exception) as source_error:
                logger.debug(
                    f"Could not extract sources from result: {source_error}. "
                    f"Falling back to tracked sources."
                )

        # Fallback: get sources from tracked search results
        tracked_sources = get_sources()
        if tracked_sources:
            logger.info(
                f"Extracted {len(tracked_sources)} sources from tracked search results"
            )
            return tracked_sources

        return []

    def _create_limit_fallback_answer(
        self, question: str, current_count: int, max_calls: int, sources_used: list[str]
    ) -> SearchAnswer:
        """Create a fallback SearchAnswer when tool call limit is reached."""
        limit_search_entry = SearchEntry(
            query=question[:QUESTION_LOG_TRUNCATE_LENGTH],
            tags=[],
            num_results=0,
            top_scores=[],
            used_ids=[],
            eval=f"limit_reached: {current_count}/{max_calls} searches completed",
        )

        return SearchAnswer(
            answer=(
                f"Agent completed {current_count} searches and reached the maximum limit. "
                f"Answer synthesized from the {current_count} search results obtained."
            ),
            confidence=LIMIT_REACHED_CONFIDENCE,  # Moderate confidence when limit is reached
            sources_used=sources_used,
            reasoning=(
                f"Completed {current_count} searches as designed. "
                f"Maximum limit of {max_calls} searches reached."
            ),
            searches=[limit_search_entry],  # At least one entry required by model
        )

    def _handle_tool_call_limit_exceeded(
        self, e: ToolCallLimitExceeded, result: Any, question: str
    ) -> SearchAgentResult:
        """Handle ToolCallLimitExceeded exception and return a valid result."""
        logger.info(
            f"Agent completed with limit: {e.current_count} searches made (max: {e.max_calls}). "
            f"This is expected and valid - agent has synthesized answer from results."
        )

        token_usage = self._extract_token_usage(result)
        sources_used = self._extract_sources_from_result(result)
        limit_answer = self._create_limit_fallback_answer(
            question, e.current_count, e.max_calls, sources_used
        )

        # Filter tool calls to only include successful ones (exclude blocked attempts)
        global _tool_calls
        successful_tool_calls = _tool_calls[: e.current_count]

        logger.info(
            f"Agent completed with limit. Tool calls: {e.current_count}, "
            f"Token usage: {token_usage.total_tokens}"
        )
        print(
            f"✅ Agent completed with limit. Made {e.current_count} tool calls (max: {e.max_calls})."
        )

        return SearchAgentResult(
            answer=limit_answer,
            tool_calls=successful_tool_calls,
            token_usage=token_usage,
        )

    async def query(self, question: str) -> SearchAgentResult:
        """
        Run agent query and return result with answer and tool calls

        Args:
            question: User question to answer

        Returns:
            SearchAgentResult - Contains answer and tool calls
        """
        self._reset_and_verify_counters()

        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        logger.info(
            f"Running agent query: {question[:QUESTION_LOG_TRUNCATE_LENGTH]}..."
        )
        print("🤖 Agent is processing your question (this may take 30-60 seconds)...")

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
            print(f"✅ Agent completed query. Made {len(_tool_calls)} tool calls.")

            try:
                log_agent_run_async(self.agent, result, question)
            except Exception as e:
                logger.warning(f"Failed to start background logging task: {e}")

            return SearchAgentResult(
                answer=result.output,
                tool_calls=_tool_calls.copy(),
                token_usage=token_usage,
            )

        except ToolCallLimitExceeded as e:
            return self._handle_tool_call_limit_exceeded(e, result, question)

        except Exception as e:
            logger.error(f"Error during agent execution: {e}")
            raise
