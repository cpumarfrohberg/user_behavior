# RAG Agent class for making repetitive tool calls
"""Main agent class that orchestrates multiple tool calls"""

import json
import logging
from typing import Any, List

from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent
from pymongo import MongoClient

from config.instructions import InstructionsConfig, InstructionType
from rag_agent.config import RAGConfig
from rag_agent.models import RAGAnswer
from rag_agent.tools import initialize_search_index, search_documents
from search.search_utils import SearchIndex
from search.simple_chunking import chunk_documents

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


class RAGAgent:
    """RAG Agent that makes repetitive tool calls for better retrieval"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.agent = None
        self.search_index = None

    def _parse_mongodb_documents(
        self, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Parse MongoDB documents into RAG format"""
        parsed_docs = []
        for doc in docs:
            # Combine title and body for content
            content_parts = []
            if doc.get("title"):
                content_parts.append(doc["title"])
            if doc.get("body"):
                content_parts.append(doc["body"])

            parsed_docs.append(
                {
                    "content": " ".join(content_parts),
                    "title": doc.get("title", ""),
                    "source": f"question_{doc.get('question_id', 'unknown')}",
                    "tags": doc.get("tags", []),
                }
            )
        return parsed_docs

    def _load_documents(
        self,
        documents: list[dict[str, Any]],
        should_chunk: bool = True,
    ) -> None:
        """Load documents into search index with chunking"""
        try:
            logger.info(f"Loading {len(documents)} documents into search index")

            # Limit documents to prevent memory issues
            max_docs = 500
            if len(documents) > max_docs:
                logger.warning(
                    f"Limiting to {max_docs} documents to prevent memory issues"
                )
                documents = documents[:max_docs]

            if should_chunk:
                # Use simple chunking function
                chunked_docs = chunk_documents(
                    documents, self.config.chunk_size, self.config.chunk_overlap
                )
                logger.info(f"Chunked documents into {len(chunked_docs)} chunks")
            else:
                chunked_docs = documents

            # Add to search index
            self.search_index.add_documents(chunked_docs)
            logger.info(
                f"Successfully loaded {len(chunked_docs)} documents into search index"
            )

        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            raise

    def _load_from_mongodb(self, should_chunk: bool = True) -> None:
        """Load documents from MongoDB and add to search index"""
        try:
            logger.info(
                f"Loading documents from MongoDB: {self.config.database}.{self.config.collection}"
            )

            # Connect to MongoDB using config
            client = MongoClient(self.config.mongo_uri)
            db = client[self.config.database]
            collection_obj = db[self.config.collection]

            # Load ALL documents
            docs = list(collection_obj.find({}, {"_id": 0}))
            logger.info(f"Loaded {len(docs)} documents from MongoDB")

            client.close()

            # Parse documents
            documents = self._parse_mongodb_documents(docs)
            logger.info(f"Parsed {len(documents)} documents for RAG")

            # Load documents into search index
            self._load_documents(documents, should_chunk=should_chunk)

        except Exception as e:
            logger.error(f"Error loading from MongoDB: {e}")
            raise

    def initialize(self) -> None:
        """Initialize search index and create agent"""
        # Initialize search index
        logger.info("Initializing search index...")
        self.search_index = SearchIndex(self.config.search_type)

        # Load documents from MongoDB
        logger.info("Loading documents from MongoDB...")
        self._load_from_mongodb(should_chunk=True)

        # Initialize the tool function with the search index
        initialize_search_index(self.search_index)

        # Set max tool calls limit from config
        from rag_agent.tools import set_max_tool_calls

        set_max_tool_calls(self.config.max_tool_calls)

        # Get instructions from config
        instructions = InstructionsConfig.INSTRUCTIONS[InstructionType.RAG_AGENT]

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
            name="rag_agent",
            model=model,
            tools=[search_documents],
            instructions=instructions,
            output_type=RAGAnswer,
            model_settings=ModelSettings(max_tokens=DEFAULT_MAX_TOKENS),
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
        # Reset tool calls for this query
        global _tool_calls
        _tool_calls = []

        # Reset tool call counter for this query
        from rag_agent.tools import reset_tool_call_count

        reset_tool_call_count()

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
        return result.output, _tool_calls.copy()
