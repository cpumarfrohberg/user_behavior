# RAG Agent class for making repetitive tool calls
"""Main agent class that orchestrates multiple tool calls"""

import json
import logging
from typing import Any, List

from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent

from config.instructions import InstructionsConfig, InstructionType
from rag_agent.tools import initialize_search_index, search_documents
from source.models import RAGAnswer
from source.text_rag import RAGConfig, TextRAG

logger = logging.getLogger(__name__)

# Store tool calls for evaluation
_tool_calls: List[dict] = []


async def track_tool_calls(ctx: Any, event: Any) -> None:
    """Event handler to track all tool calls for evaluation"""
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

        # Parse args to extract query for display (args is JSON string in pydantic-ai)
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
            f"🔧 Tool Call #{tool_num}: {event.part.tool_name} with args: {event.part.args}"
        )


class RAGAgent:
    """RAG Agent that makes repetitive tool calls for better retrieval"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.agent = None
        self.search_index = None

    def initialize(self) -> None:
        """Initialize search index and create agent"""
        # Initialize search index by loading documents from MongoDB
        logger.info("Initializing search index with documents from MongoDB...")

        # Use existing TextRAG to load documents
        text_rag = TextRAG(self.config)
        text_rag.load_from_mongodb(should_chunk=True)

        # Get the search index that was loaded
        self.search_index = text_rag.search_index

        # Initialize the tool function with the search index
        initialize_search_index(self.search_index)

        # Get instructions from config
        instructions = InstructionsConfig.INSTRUCTIONS[InstructionType.RAG_AGENT]

        # Initialize Ollama model (local, data privacy)
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        from config import OLLAMA_HOST

        # Use Ollama via OpenAI-compatible interface (local inference)
        # OLLAMA_HOST should be "http://ollama:11434" for Docker or "http://localhost:11434" for local
        ollama_base_url = f"{OLLAMA_HOST}/v1"
        model = OpenAIChatModel(
            model_name=self.config.ollama_model,
            provider=OpenAIProvider(base_url=ollama_base_url),
        )
        logger.info(
            f"Using Ollama model: {self.config.ollama_model} at {ollama_base_url}"
        )

        # Create agent
        self.agent = Agent(
            name="rag_agent",
            model=model,
            tools=[search_documents],
            instructions=instructions,
            output_type=RAGAnswer,
        )

        logger.info("RAG Agent initialized successfully")

    async def query(self, question: str) -> tuple[RAGAnswer, List[dict]]:
        """
        Run agent query and return answer + tool calls

        Args:
            question: User question to answer

        Returns:
            (answer, tool_calls) - Answer object and list of tool calls for evaluation
        """
        global _tool_calls
        _tool_calls = []  # Reset for each query

        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        logger.info(f"Running agent query: {question[:100]}...")
        print("🤖 Agent is processing your question (this may take 30-60 seconds)...")

        # Run agent with event tracking
        result = None
        try:
            result = await self.agent.run(
                question,
                event_stream_handler=track_tool_calls,
            )
        except Exception as e:
            logger.error(f"Error during agent.run(): {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")

            # Try to get more details about validation errors
            if hasattr(e, "args") and e.args:
                logger.error(f"Error args: {e.args}")
            if hasattr(e, "__cause__") and e.__cause__:
                logger.error(f"Caused by: {e.__cause__}")

            # Log the raw result if available (only if result was created)
            if result is not None:
                try:
                    # Try to get partial result if available
                    if hasattr(result, "output"):
                        logger.error(f"Partial output: {result.output}")
                    if hasattr(result, "data"):
                        logger.error(f"Result data: {result.data}")
                except Exception as log_err:
                    logger.error(f"Could not log result details: {log_err}")
            else:
                logger.error(
                    "No result object available (exception occurred before completion)"
                )

            print(f"❌ Error during agent execution: {e}")
            print("📋 Check logs for detailed error information")
            raise

        logger.info(f"Agent completed query. Tool calls: {len(_tool_calls)}")
        print(f"✅ Agent completed query. Made {len(_tool_calls)} tool calls.")
        return result.output, _tool_calls.copy()
