# MongoDB Agent class for making repetitive tool calls
"""Main agent class that orchestrates multiple tool calls"""

import json
import logging
from typing import Any, List

from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent
from pymongo import MongoClient

from config.instructions import InstructionsConfig, InstructionType
from mongodb_agent.config import MongoDBConfig
from mongodb_agent.models import SearchAgentResult, SearchAnswer
from mongodb_agent.tools import search_mongodb

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

        # Initialize the tool function with MongoDB collection
        from mongodb_agent.tools import initialize_mongodb_collection

        initialize_mongodb_collection(self.collection)

        # Set max tool calls limit from config
        from mongodb_agent.tools import set_max_tool_calls

        set_max_tool_calls(self.config.max_tool_calls)

        # Get instructions from config
        instructions = InstructionsConfig.INSTRUCTIONS[InstructionType.MONGODB_AGENT]

        # Initialize OpenAI model
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        # Use OpenAI provider (no base_url needed for OpenAI API)
        model = OpenAIChatModel(
            model_name=self.config.openai_model,
            provider=OpenAIProvider(),
        )
        logger.info(f"Using OpenAI model: {self.config.openai_model}")

        # Create agent with max_tokens limit for speed
        from pydantic_ai import ModelSettings

        from config import DEFAULT_MAX_TOKENS

        self.agent = Agent(
            name="mongodb_agent",
            model=model,
            tools=[search_mongodb],
            instructions=instructions,
            output_type=SearchAnswer,
            model_settings=ModelSettings(max_tokens=DEFAULT_MAX_TOKENS),
        )

        logger.info("MongoDB Agent initialized successfully")

    async def query(self, question: str) -> SearchAgentResult:
        """
        Run agent query and return result with answer and tool calls

        Args:
            question: User question to answer

        Returns:
            SearchAgentResult - Contains answer and tool calls
        """
        # Reset tool calls for this query
        global _tool_calls
        _tool_calls = []

        # Reset tool call counter for this query
        from mongodb_agent.tools import get_tool_call_count, reset_tool_call_count

        reset_tool_call_count()
        # Verify counter is reset to 0
        initial_count = get_tool_call_count()
        if initial_count != 0:
            logger.warning(
                f"⚠️ Counter not properly reset! Expected 0, got {initial_count}. "
                f"Resetting again..."
            )
            reset_tool_call_count()
            initial_count = get_tool_call_count()
        logger.info(f"✅ Tool call counter reset to {initial_count} (verified)")

        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        logger.info(f"Running agent query: {question[:100]}...")
        print("🤖 Agent is processing your question (this may take 30-60 seconds)...")

        # Run agent with event tracking
        try:
            result = await self.agent.run(
                question,
                event_stream_handler=track_tool_calls,
            )
        except Exception as e:
            logger.error(f"Error during agent execution: {e}")
            raise

        logger.info(f"Agent completed query. Tool calls: {len(_tool_calls)}")
        print(f"✅ Agent completed query. Made {len(_tool_calls)} tool calls.")

        # Log agent run to database (non-blocking background task)
        try:
            from monitoring.agent_logging import log_agent_run_async

            log_agent_run_async(self.agent, result, question)
        except Exception as e:
            logger.warning(f"Failed to start background logging task: {e}")

        return SearchAgentResult(
            answer=result.output,
            tool_calls=_tool_calls.copy(),
        )
