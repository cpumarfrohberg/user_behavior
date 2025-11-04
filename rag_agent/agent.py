# RAG Agent class for making repetitive tool calls
"""Main agent class that orchestrates multiple tool calls"""

import json
import logging
from typing import Any, List

from pydantic_ai import Agent
from pydantic_ai.messages import (
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
)

from config.instructions import InstructionsConfig, InstructionType
from rag_agent.tools import initialize_search_index, search_documents
from source.models import RAGAnswer
from source.text_rag import RAGConfig, TextRAG

logger = logging.getLogger(__name__)

# Store tool calls for evaluation
_tool_calls: List[dict] = []
# Store accumulated text output for debugging
_accumulated_text: str = ""


async def track_tool_calls(ctx: Any, event: Any) -> None:
    """Event handler to track all tool calls and capture model output text"""
    global _accumulated_text, _tool_calls

    # Handle nested async streams
    if hasattr(event, "__aiter__"):
        async for sub in event:
            await track_tool_calls(ctx, sub)
        return

    # Log all event types for debugging
    event_type = type(event).__name__
    logger.debug(f"📨 Event received: {event_type}")

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
            f"🔧 Tool Call #{tool_num}: {event.part.tool_name} with args: {event.part.args}"
        )

    # Accumulate text from delta events - this captures the raw model output
    if isinstance(event, PartDeltaEvent):
        # Track accumulation state before processing
        text_before = len(_accumulated_text)
        logger.debug(
            f"PartDeltaEvent received, delta type: {type(event.delta) if hasattr(event, 'delta') else 'no delta attr'}, accumulated so far: {text_before} chars"
        )
        try:
            delta = event.delta

            # TextPartDelta - try multiple possible attribute names
            if isinstance(delta, TextPartDelta):
                # Try common attribute names for text content
                text_chunk = None
                for attr in ["text_delta", "text", "content_delta", "content", "delta"]:
                    if hasattr(delta, attr):
                        value = getattr(delta, attr)
                        if value:
                            text_chunk = value
                            logger.debug(
                                f"Found text in TextPartDelta.{attr}: {len(str(value))} chars, value: {repr(str(value)[:50])}"
                            )
                            break

                if text_chunk:
                    _accumulated_text += str(text_chunk)
                    text_after = len(_accumulated_text)
                    logger.debug(
                        f"✓ Accumulated: {text_before} → {text_after} chars (+{text_after - text_before})"
                    )
            # Fallback: try direct string conversion or other attributes
            elif isinstance(delta, str):
                _accumulated_text += delta
                text_after = len(_accumulated_text)
                logger.debug(
                    f"✓ Captured string delta: {len(delta)} chars, accumulated: {text_before} → {text_after} chars, value: {repr(delta[:50])}"
                )
            else:
                # Try common text attributes on any delta type
                for attr in ["text", "content", "data", "value"]:
                    if hasattr(delta, attr):
                        value = getattr(delta, attr)
                        if value and isinstance(value, str):
                            _accumulated_text += value
                            text_after = len(_accumulated_text)
                            logger.debug(
                                f"✓ Captured text from delta.{attr}: {len(value)} chars, accumulated: {text_before} → {text_after} chars, value: {repr(value[:50])}"
                            )
                            break
        except Exception as e:
            logger.debug(
                f"Error extracting text from delta: {e}, delta type: {type(event.delta) if hasattr(event, 'delta') else 'N/A'}"
            )

    # Capture output from final result
    if isinstance(event, FinalResultEvent):
        try:
            if hasattr(event, "result") and hasattr(event.result, "output"):
                output = event.result.output
                if hasattr(output, "data"):
                    _accumulated_text += str(output.data)
                elif hasattr(output, "text"):
                    _accumulated_text += str(output.text)
        except Exception as e:
            logger.debug(f"Error extracting text from final result: {e}")


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
        # Declare global variables at the top of the method
        global _tool_calls, _accumulated_text
        _tool_calls = []  # Reset for each query
        _accumulated_text = ""  # Reset accumulated text

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
            logger.error(f"Error during agent.run(): {e}")
            logger.error(f"Error type: {type(e).__name__}")

            # If we didn't capture text from events, try to extract from exception
            if not _accumulated_text:
                logger.debug("Attempting to extract model output from exception...")

                # Try to extract from exception cause (ToolRetryError)
                if hasattr(e, "__cause__") and e.__cause__:
                    cause = e.__cause__

                    # Check for tool_retry with model_response
                    if hasattr(cause, "tool_retry"):
                        tool_retry = cause.tool_retry
                        if hasattr(tool_retry, "model_response"):
                            try:
                                # model_response might be callable or a property
                                model_response = (
                                    tool_retry.model_response()
                                    if callable(tool_retry.model_response)
                                    else tool_retry.model_response
                                )

                                # Extract text from model_response parts
                                if hasattr(model_response, "parts"):
                                    for part in model_response.parts:
                                        if hasattr(part, "text") and part.text:
                                            text = str(part.text)
                                            if (
                                                text
                                                and text
                                                != "Please include your response in a tool call."
                                            ):
                                                _accumulated_text = text
                                                break
                                        elif hasattr(part, "content") and part.content:
                                            content = str(part.content)
                                            if (
                                                content
                                                and content
                                                != "Please include your response in a tool call."
                                            ):
                                                _accumulated_text = content
                                                break

                                # Try direct attributes
                                if not _accumulated_text:
                                    for attr in ["text", "content"]:
                                        if hasattr(model_response, attr):
                                            value = getattr(model_response, attr)
                                            if (
                                                value
                                                and str(value)
                                                != "Please include your response in a tool call."
                                            ):
                                                _accumulated_text = str(value)
                                                break
                            except Exception as extract_err:
                                logger.debug(
                                    f"Could not extract from model_response: {extract_err}"
                                )

                    # Try to extract from last_assistant_message
                    if not _accumulated_text and hasattr(
                        cause, "last_assistant_message"
                    ):
                        msg = cause.last_assistant_message
                        if msg and hasattr(msg, "parts"):
                            for part in msg.parts:
                                for attr in ["text", "content"]:
                                    if hasattr(part, attr):
                                        value = getattr(part, attr)
                                        if (
                                            value
                                            and str(value)
                                            != "Please include your response in a tool call."
                                        ):
                                            _accumulated_text = str(value)
                                            break
                                if _accumulated_text:
                                    break

            # Log captured output for debugging
            if _accumulated_text:
                logger.error(
                    f"📝 Captured model output ({len(_accumulated_text)} chars): {_accumulated_text[:500]}..."
                )
                print(
                    f"📝 DEBUG: Captured {len(_accumulated_text)} chars of model output"
                )
                print(f"📝 First 500 chars: {_accumulated_text[:500]}")

                # Try to extract and validate JSON
                text_to_parse = _accumulated_text.strip()

                # Extract from markdown code blocks if present
                if text_to_parse.startswith("```"):
                    import re

                    json_match = re.search(
                        r"```(?:json)?\s*(.*?)\s*```", text_to_parse, re.DOTALL
                    )
                    if json_match:
                        text_to_parse = json_match.group(1).strip()

                # Try to parse and validate JSON
                try:
                    parsed = json.loads(text_to_parse)
                    logger.error("📝 JSON is valid. Checking schema...")

                    if isinstance(parsed, dict):
                        required_fields = ["answer", "confidence", "sources_used"]
                        missing = [f for f in required_fields if f not in parsed]
                        if missing:
                            logger.error(f"📝 Missing fields: {missing}")
                        else:
                            logger.error(
                                f"📝 Schema validation: answer={type(parsed.get('answer'))}, confidence={type(parsed.get('confidence'))}, sources_used={type(parsed.get('sources_used'))}"
                            )
                except json.JSONDecodeError as je:
                    logger.error(f"📝 JSON parse error: {je.msg} at position {je.pos}")
            else:
                logger.error(
                    "📝 No model output captured - event handler may not be receiving delta events"
                )
                print("📝 DEBUG: No model output was captured from events")

            print(f"❌ Error during agent execution: {e}")
            raise

        logger.info(f"Agent completed query. Tool calls: {len(_tool_calls)}")
        print(f"✅ Agent completed query. Made {len(_tool_calls)} tool calls.")
        return result.output, _tool_calls.copy()
