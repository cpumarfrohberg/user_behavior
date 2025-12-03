import asyncio
import json
import logging
from typing import Any

import streamlit as st

from config import LOG_LEVEL
from monitoring.db import get_cost_stats, get_recent_logs, init_db
from orchestrator.agent import OrchestratorAgent
from orchestrator.config import OrchestratorConfig
from orchestrator.models import OrchestratorAnswer

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

st.set_page_config(page_title="User Behavior Agent", page_icon="🤖", layout="wide")

# Initialize session state
st.session_state.setdefault("messages", [])
st.session_state.setdefault("db_initialized", False)
st.session_state.setdefault("orchestrator_agent", None)

# Initialize database
if not st.session_state.db_initialized:
    init_db()
    st.session_state.db_initialized = True


def _get_orchestrator_agent() -> OrchestratorAgent:
    """Get or initialize Orchestrator Agent"""
    if st.session_state.orchestrator_agent is None:
        config = OrchestratorConfig()
        agent = OrchestratorAgent(config)
        agent.initialize()
        st.session_state.orchestrator_agent = agent
    return st.session_state.orchestrator_agent


async def run_agent_stream(
    question: str,
    answer_container: Any,
    confidence_container: Any,
    reasoning_container: Any,
    sources_container: Any,
    agents_container: Any,
    tool_calls_container: Any,
) -> OrchestratorAnswer | None:
    """Run orchestrator agent with tool call tracking."""
    agent_instance = _get_orchestrator_agent()
    tool_calls_list = []

    def _handle_tool_call(tool_name: str, args: str) -> None:
        """Handle tool call events"""
        try:
            args_dict = json.loads(args) if isinstance(args, str) else args
            query = (
                args_dict.get("question", args_dict.get("query", "N/A"))
                if isinstance(args_dict, dict)
                else str(args)
            )[:50]
        except (json.JSONDecodeError, AttributeError, TypeError):
            query = str(args)[:50] if args else "N/A"
        tool_calls_list.append({"tool_name": tool_name, "query": query})
        tool_calls_text = "\n".join(
            f"🔍 {i+1}. **{c['tool_name']}**: {c['query']}..."
            for i, c in enumerate(tool_calls_list)
        )
        tool_calls_container.markdown(tool_calls_text)

    def _create_tool_call_tracker() -> Any:
        """Create tool call tracker for event handler"""
        from pydantic_ai.messages import FunctionToolCallEvent

        async def track_handler(ctx: Any, event: Any) -> None:
            """Track tool calls and call callback"""
            if hasattr(event, "__aiter__"):
                async for sub in event:
                    await track_handler(ctx, sub)
                return

            if isinstance(event, FunctionToolCallEvent):
                tool_name = event.part.tool_name
                args = event.part.args
                _handle_tool_call(tool_name, args)

        return track_handler

    try:
        # Run agent with tool call tracking
        result = await agent_instance.agent.run(
            question, event_stream_handler=_create_tool_call_tracker()
        )

        # Display results
        answer = result.output
        if answer:
            answer_container.markdown(answer.answer)
            if answer.confidence is not None:
                confidence_container.metric("Confidence", f"{answer.confidence:.2%}")
            if answer.reasoning:
                reasoning_container.markdown(f"**Reasoning:** {answer.reasoning}")
            if answer.sources_used:
                sources_text = "\n".join(f"- {s}" for s in answer.sources_used)
                sources_container.markdown(f"**Sources:**\n{sources_text}")
            if answer.agents_used:
                agents_text = ", ".join(answer.agents_used)
                agents_container.markdown(f"**Agents Used:** {agents_text}")

        st.session_state.last_result = answer
        st.session_state.tool_calls = tool_calls_list
        return answer
    except Exception as e:
        logging.error(f"Error running agent: {e}", exc_info=True)
        st.error(f"Error: {e}")
        return None


def main() -> None:
    st.title("🤖 User Behavior Agent")

    with st.sidebar:
        st.header("Navigation")
        nav = st.radio(
            "Page", ["Chat", "Monitoring", "About"], label_visibility="collapsed"
        )
        st.divider()

        if nav == "Chat":
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.last_result = None
                st.rerun()

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
    if not st.session_state.messages:
        st.info("👋 Ask a question about user behavior patterns!")

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
            tool_calls_container.info("🤖 Processing...")

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
                    st.session_state.messages.append(
                        {"role": "assistant", "content": result.answer}
                    )
            except Exception as e:
                st.error(f"Error: {e}")
                logging.error(f"Error in chat: {e}", exc_info=True)


def _render_monitoring_page() -> None:
    st.header("📊 Monitoring Dashboard")

    # Cost Statistics
    st.subheader("💰 Cost Statistics")
    try:
        stats = get_cost_stats()
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
        logs = get_recent_logs(limit=20)
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
