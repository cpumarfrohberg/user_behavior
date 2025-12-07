import asyncio
import json
import logging
from typing import Any

import streamlit as st
from jaxn import StreamingJSONParser
from pydantic_ai.messages import FunctionToolCallEvent

from config import LOG_LEVEL
from monitoring.db import get_cost_stats, get_recent_logs, init_db
from orchestrator.agent import OrchestratorAgent
from orchestrator.config import OrchestratorConfig
from orchestrator.models import OrchestratorAnswer
from stream_handler import OrchestratorAnswerHandler

# Streaming performance constants
STREAM_DEBOUNCE = 0.01  # Debounce streaming updates (seconds)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

st.set_page_config(page_title="User Behavior Agent", page_icon="🤖", layout="wide")

# Initialize session state
st.session_state.setdefault("messages", [])
st.session_state.setdefault("tool_calls", [])
st.session_state.setdefault("last_result", None)


# Cache database initialization (runs once per session)
@st.cache_resource
def _init_database():
    """Initialize database - cached across reruns"""
    init_db()
    return True


# Initialize database (cached)
_init_database()


@st.cache_resource
def _get_orchestrator_agent() -> OrchestratorAgent:
    """Get or initialize Orchestrator Agent - cached across reruns"""
    config = OrchestratorConfig()
    agent = OrchestratorAgent(config)
    agent.initialize()
    return agent


async def run_agent_stream(
    question: str,
    answer_container: Any,
    confidence_container: Any,
    reasoning_container: Any,
    sources_container: Any,
    agents_container: Any,
    tool_calls_container: Any,
) -> OrchestratorAnswer | None:
    """Run orchestrator agent with streaming output and tool call tracking."""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting agent stream for question: {question[:100]}...")

    orchestrator_agent = _get_orchestrator_agent()
    st.session_state.tool_calls = []  # Reset tool calls for new query

    # Initialize streaming JSON parser with handler
    handler = OrchestratorAnswerHandler(
        answer_container=answer_container,
        confidence_container=confidence_container,
        reasoning_container=reasoning_container,
        sources_container=sources_container,
        agents_container=agents_container,
    )
    handler.reset()
    parser = StreamingJSONParser(handler)

    logger.info("Streaming parser and handler initialized")

    async def _handle_tool_call(ctx: Any, event: Any) -> None:
        """Event handler to track and display tool calls."""
        # Handle nested events (event streams)
        if hasattr(event, "__aiter__"):
            async for sub in event:
                await _handle_tool_call(ctx, sub)
            return

        # Handle FunctionToolCallEvent
        if isinstance(event, FunctionToolCallEvent):
            tool_call = {
                "tool_name": event.part.tool_name,
                "args": event.part.args,
            }
            st.session_state.tool_calls.append(tool_call)
            tool_calls_text = "\n".join(
                f"🔍 {i+1}. **{c['tool_name']}**: {str(c['args'])[:50]}..."
                for i, c in enumerate(st.session_state.tool_calls)
            )
            tool_calls_container.markdown(tool_calls_text)

    try:
        # Run agent with streaming
        logger.info("Starting orchestrator agent run_stream...")
        async with orchestrator_agent.agent.run_stream(
            question, event_stream_handler=_handle_tool_call
        ) as result:
            logger.info("Agent stream context entered, starting to stream responses...")
            text_chunks_received = 0
            total_text_length = 0

            # Stream responses and parse JSON incrementally with debouncing
            async for item, last in result.stream_responses(
                debounce_by=STREAM_DEBOUNCE
            ):
                for part in item.parts:
                    # Extract text from streaming parts and feed to parser
                    # pydantic-ai streams structured output as text parts
                    if hasattr(part, "text") and part.text:
                        text_chunks_received += 1
                        total_text_length += len(part.text)
                        logger.debug(
                            f"Received text chunk #{text_chunks_received} (length: {len(part.text)}, total: {total_text_length}): {part.text[:200]}..."
                        )
                        try:
                            parser.parse_incremental(part.text)
                        except Exception as parse_error:
                            # Log parsing errors with details instead of silently ignoring
                            logger.warning(
                                f"JSON parsing error on chunk #{text_chunks_received}: {parse_error}. "
                                f"Chunk preview: {part.text[:100]}..."
                            )
                            # Still pass - this is expected for incomplete JSON chunks
                            pass

            logger.info(
                f"Streaming completed. Received {text_chunks_received} text chunks, "
                f"total length: {total_text_length} characters"
            )

            # Log handler state after streaming
            logger.info(
                f"Handler state after streaming - "
                f"answer: {len(handler.current_answer) if handler.current_answer else 0} chars, "
                f"confidence: {handler.current_confidence}, "
                f"reasoning: {len(handler.current_reasoning) if handler.current_reasoning else 0} chars, "
                f"agents: {handler.agents_list}, "
                f"sources: {len(handler.sources_list) if handler.sources_list else 0} items"
            )

            # Try to construct output from handler state (faster than re-parsing)
            # Only call get_output() if handler parsing failed or is incomplete
            try:
                handler_complete = (
                    handler.current_answer
                    and handler.current_confidence is not None
                    and handler.current_reasoning
                    and handler.agents_list
                )

                if handler_complete:
                    logger.info(
                        "Handler state is complete, constructing OrchestratorAnswer from handler state"
                    )
                    # Construct from handler state (already parsed during streaming)
                    final_output = OrchestratorAnswer(
                        answer=handler.current_answer,
                        confidence=handler.current_confidence,
                        reasoning=handler.current_reasoning,
                        agents_used=handler.agents_list,
                        sources_used=handler.sources_list
                        if handler.sources_list
                        else None,
                    )
                    logger.info(
                        f"Successfully constructed OrchestratorAnswer from handler state"
                    )
                else:
                    logger.warning(
                        f"Handler state incomplete - missing: "
                        f"answer={not handler.current_answer}, "
                        f"confidence={handler.current_confidence is None}, "
                        f"reasoning={not handler.current_reasoning}, "
                        f"agents={not handler.agents_list}. "
                        f"Falling back to get_output()..."
                    )
                    # Fallback: handler parsing incomplete, use get_output()
                    final_output = await result.get_output()
                    logger.info(
                        f"get_output() returned: type={type(final_output)}, value={final_output}"
                    )
            except Exception as construct_error:
                # If construction fails, fall back to get_output()
                logger.error(
                    f"Error constructing OrchestratorAnswer from handler state: {construct_error}. "
                    f"Falling back to get_output()...",
                    exc_info=True,
                )
                try:
                    final_output = await result.get_output()
                    logger.info(
                        f"get_output() returned after error: type={type(final_output)}, value={final_output}"
                    )
                except Exception as get_output_error:
                    logger.error(
                        f"get_output() also failed: {get_output_error}", exc_info=True
                    )
                    raise
        st.session_state.last_result = final_output

        logger.info(
            f"Final output type: {type(final_output)}, "
            f"is None: {final_output is None}"
        )
        if final_output:
            logger.info(
                f"Final output content - "
                f"answer length: {len(final_output.answer) if hasattr(final_output, 'answer') else 'N/A'}, "
                f"confidence: {final_output.confidence if hasattr(final_output, 'confidence') else 'N/A'}, "
                f"agents: {final_output.agents_used if hasattr(final_output, 'agents_used') else 'N/A'}"
            )

        # Ensure all containers are updated with final values
        logger.info("Updating UI containers with final values...")
        containers_updated = 0

        if handler.answer_container and handler.current_answer:
            # Filter stats from answer text
            import re

            answer_text = handler.current_answer
            answer_text = re.sub(
                r"(?i)(confidence|onfidence)\s*:?\s*\d+\.?\d*%?\s*\n?", "", answer_text
            )
            answer_text = re.sub(r"(?i)reasoning\s*:?\s*[^\n]+\n?", "", answer_text)
            answer_text = re.sub(
                r"(?i)agents?\s+used\s*:?\s*[^\n]+\n?", "", answer_text
            )
            handler.answer_container.markdown(answer_text.strip())
            containers_updated += 1
            logger.info("Updated answer container")
        elif (
            handler.answer_container
            and final_output
            and hasattr(final_output, "answer")
        ):
            # Filter stats from answer text
            import re

            answer_text = final_output.answer
            answer_text = re.sub(
                r"(?i)(confidence|onfidence)\s*:?\s*\d+\.?\d*%?\s*\n?", "", answer_text
            )
            answer_text = re.sub(r"(?i)reasoning\s*:?\s*[^\n]+\n?", "", answer_text)
            answer_text = re.sub(
                r"(?i)agents?\s+used\s*:?\s*[^\n]+\n?", "", answer_text
            )
            handler.answer_container.markdown(answer_text.strip())
            containers_updated += 1
            logger.info("Updated answer container from final_output")
        else:
            logger.warning("Answer container not updated - no answer available")

        if handler.confidence_container and handler.current_confidence is not None:
            handler.confidence_container.metric(
                "Confidence", f"{handler.current_confidence:.2%}"
            )
            containers_updated += 1
            logger.info("Updated confidence container")
        elif (
            handler.confidence_container
            and final_output
            and hasattr(final_output, "confidence")
        ):
            handler.confidence_container.metric(
                "Confidence", f"{final_output.confidence:.2%}"
            )
            containers_updated += 1
            logger.info("Updated confidence container from final_output")
        else:
            logger.warning(
                "Confidence container not updated - no confidence value available"
            )

        if handler.reasoning_container and handler.current_reasoning:
            handler.reasoning_container.markdown(
                f"**Reasoning:** {handler.current_reasoning}"
            )
            containers_updated += 1
            logger.info("Updated reasoning container")
        elif (
            handler.reasoning_container
            and final_output
            and hasattr(final_output, "reasoning")
        ):
            handler.reasoning_container.markdown(
                f"**Reasoning:** {final_output.reasoning}"
            )
            containers_updated += 1
            logger.info("Updated reasoning container from final_output")
        else:
            logger.warning("Reasoning container not updated - no reasoning available")

        if handler.sources_container and handler.sources_list:
            sources_text = "\n".join(f"- {s}" for s in handler.sources_list)
            handler.sources_container.markdown(f"**Sources:**\n{sources_text}")
            containers_updated += 1
            logger.info(
                f"Updated sources container with {len(handler.sources_list)} sources"
            )
        elif (
            handler.sources_container
            and final_output
            and hasattr(final_output, "sources_used")
            and final_output.sources_used
        ):
            sources_text = "\n".join(f"- {s}" for s in final_output.sources_used)
            handler.sources_container.markdown(f"**Sources:**\n{sources_text}")
            containers_updated += 1
            logger.info(
                f"Updated sources container from final_output with {len(final_output.sources_used)} sources"
            )
        else:
            logger.warning("Sources container not updated - no sources available")

        if handler.agents_container and handler.agents_list:
            agents_text = ", ".join(handler.agents_list)
            handler.agents_container.markdown(f"**Agents Used:** {agents_text}")
            containers_updated += 1
            logger.info("Updated agents container")
        elif (
            handler.agents_container
            and final_output
            and hasattr(final_output, "agents_used")
        ):
            agents_text = ", ".join(final_output.agents_used)
            handler.agents_container.markdown(f"**Agents Used:** {agents_text}")
            containers_updated += 1
            logger.info("Updated agents container from final_output")
        else:
            logger.warning("Agents container not updated - no agents list available")

        logger.info(
            f"Updated {containers_updated} UI containers. Returning final_output."
        )
        return final_output
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        logger.error(f"Exception type: {type(e).__name__}, message: {str(e)}")
        st.error(f"⚠️ An error occurred: {e}")
        st.info("Please try again or rephrase your question.")
        return None


def main() -> None:
    st.title("🤖 User Behavior Agent")

    with st.sidebar:
        st.header("Navigation")
        nav = st.radio(
            "Select a page", ["About", "Chat", "Monitoring"], label_visibility="visible"
        )
        st.divider()

    if nav == "About":
        _render_about_page()
    elif nav == "Monitoring":
        _render_monitoring_page()
    else:  # Chat
        _render_chat_page()


def _render_about_page() -> None:
    st.markdown("## Welcome to User Behavior Agent")
    st.markdown(
        "Ask questions about user behavior patterns from StackExchange discussions!"
    )
    st.markdown("### How it works:")
    st.markdown("1. Ask a question about user behavior, UX patterns, or relationships")
    st.markdown(
        "2. The orchestrator routes your question to the appropriate agent (MongoDB for content, Cypher for relationships)"
    )
    st.markdown("3. Get real-time streaming answers with sources and reasoning")
    st.divider()
    st.markdown("### Example Questions:")
    for q in [
        "What are common user frustration patterns?",
        "How do users react to confusing interfaces?",
        "Which users have the most interactions?",
        "What topics are most discussed?",
    ]:
        st.markdown(f"- {q}")


def _render_chat_page() -> None:
    with st.sidebar:
        st.header("Configuration")
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.tool_calls = []
            st.session_state.last_result = None
            st.rerun()
        st.divider()
        st.header("Statistics")
        result = st.session_state.get("last_result")
        if result:
            if hasattr(result, "confidence") and result.confidence is not None:
                st.metric("Confidence", f"{result.confidence:.2%}")
            if hasattr(result, "agents_used") and result.agents_used:
                st.markdown(f"**Agents Used:** {', '.join(result.agents_used)}")
        else:
            st.info("No queries yet. Ask a question to see stats.")

    if not st.session_state.messages:
        st.info("👋 Start a conversation by asking a question about user behavior!")

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question about user behavior..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # Create containers for streaming
            answer_container = st.empty()
            tool_calls_container = st.empty()
            tool_calls_container.info("🤖 Agent is processing your question...")

            col1, col2 = st.columns([2, 1])
            with col1:
                sources_container = st.empty()
            with col2:
                confidence_container = st.empty()
                reasoning_container = st.empty()
                agents_container = st.empty()

            try:
                result = asyncio.run(
                    run_agent_stream(
                        prompt,
                        answer_container,
                        confidence_container,
                        reasoning_container,
                        sources_container,
                        agents_container,
                        tool_calls_container,
                    )
                )

                if result:
                    # Save answer to chat history (filter out stats)
                    import re

                    answer_text = result.answer
                    answer_text = re.sub(
                        r"(?i)(confidence|onfidence)\s*:?\s*\d+\.?\d*%?\s*\n?",
                        "",
                        answer_text,
                    )
                    answer_text = re.sub(
                        r"(?i)reasoning\s*:?\s*[^\n]+\n?", "", answer_text
                    )
                    answer_text = re.sub(
                        r"(?i)agents?\s+used\s*:?\s*[^\n]+\n?", "", answer_text
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer_text.strip()}
                    )
                    # Clear processing message
                    tool_calls_container.empty()
            except Exception as e:
                st.error(f"Error: {e}")
                logging.error(f"Error in chat: {e}", exc_info=True)
                tool_calls_container.empty()


@st.cache_data(ttl=30)  # Cache for 30 seconds to reduce DB queries
def _get_cached_cost_stats():
    """Get cost statistics with caching"""
    return get_cost_stats()


@st.cache_data(ttl=30)  # Cache for 30 seconds to reduce DB queries
def _get_cached_recent_logs(limit: int = 20):
    """Get recent logs with caching"""
    return get_recent_logs(limit=limit)


def _render_monitoring_page() -> None:
    st.header("📊 Monitoring Dashboard")

    # Cost Statistics
    st.subheader("💰 Cost Statistics")
    try:
        stats = _get_cached_cost_stats()
        if stats:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Cost", f"${stats['total_cost']:.4f}")
            col2.metric("Total Queries", stats["total_queries"])
            col3.metric("Average Cost", f"${stats['avg_cost']:.4f}")
        else:
            st.info("No cost data available yet.")
    except Exception as e:
        st.error(f"Error loading statistics: {e}")

    st.divider()

    # Recent Logs
    st.subheader("📝 Recent Logs")
    try:
        logs = _get_cached_recent_logs(limit=20)
        if logs:
            for log in logs:
                with st.expander(
                    f"Log #{log.get('id')} - {log.get('user_prompt', 'N/A')[:50]}..."
                ):
                    st.write(f"**Time:** {log.get('created_at')}")
                    st.write(f"**Agent:** {log.get('agent_name', 'N/A')}")
                    st.write(f"**Model:** {log.get('model', 'N/A')}")
                    st.write(
                        f"**Cost:** ${log.get('total_cost', 0):.4f}"
                        if log.get("total_cost")
                        else "**Cost:** N/A"
                    )
                    st.write(
                        f"**Tokens:** {log.get('total_input_tokens', 'N/A')} in / {log.get('total_output_tokens', 'N/A')} out"
                    )
        else:
            st.info("No logs available yet.")
    except Exception as e:
        st.error(f"Error loading logs: {e}")


if __name__ == "__main__":
    main()
