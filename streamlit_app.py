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
        async with orchestrator_agent.agent.run_stream(
            question, event_stream_handler=_handle_tool_call
        ) as result:
            # Stream responses and parse JSON incrementally with debouncing
            async for item, last in result.stream_responses(
                debounce_by=STREAM_DEBOUNCE
            ):
                for part in item.parts:
                    # Extract text from streaming parts and feed to parser
                    # pydantic-ai streams structured output as text parts
                    if hasattr(part, "text") and part.text:
                        try:
                            parser.parse_incremental(part.text)
                        except Exception:
                            # Ignore parsing errors for incomplete JSON chunks
                            # This is expected as JSON may be incomplete during streaming
                            pass

            # Try to construct output from handler state (faster than re-parsing)
            # Only call get_output() if handler parsing failed or is incomplete
            try:
                if (
                    handler.current_answer
                    and handler.current_confidence is not None
                    and handler.current_reasoning
                    and handler.agents_list
                ):
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
                else:
                    # Fallback: handler parsing incomplete, use get_output()
                    final_output = await result.get_output()
            except Exception:
                # If construction fails, fall back to get_output()
                final_output = await result.get_output()
        st.session_state.last_result = final_output

        # Ensure all containers are updated with final values
        if handler.answer_container and handler.current_answer:
            handler.answer_container.markdown(handler.current_answer)
        if handler.confidence_container and handler.current_confidence is not None:
            handler.confidence_container.metric(
                "Confidence", f"{handler.current_confidence:.2%}"
            )
        if handler.reasoning_container and handler.current_reasoning:
            handler.reasoning_container.markdown(
                f"**Reasoning:** {handler.current_reasoning}"
            )
        if handler.sources_container and handler.sources_list:
            sources_text = "\n".join(f"- {s}" for s in handler.sources_list)
            handler.sources_container.markdown(f"**Sources:**\n{sources_text}")
        if handler.agents_container and handler.agents_list:
            agents_text = ", ".join(handler.agents_list)
            handler.agents_container.markdown(f"**Agents Used:** {agents_text}")

        return final_output
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error during agent execution: {e}", exc_info=True)
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
                    # Save answer to chat history
                    st.session_state.messages.append(
                        {"role": "assistant", "content": result.answer}
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
