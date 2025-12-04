import asyncio
import json
import logging
from typing import Any

import pydantic
from genai_prices import Usage, calc_price
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.result import StreamedRunResult
from pydantic_ai.usage import RunUsage

from monitoring.db import get_db, insert_log
from monitoring.schemas import LogCreate

logger = logging.getLogger(__name__)

UsageTypeAdapter = pydantic.TypeAdapter(RunUsage)


def _create_log_entry(
    agent: Agent,
    messages: list[ModelMessage],
    usage: RunUsage,
    output: Any,
) -> dict:
    """Extract log data from agent execution."""
    tools = []
    for ts in agent.toolsets:
        tools.extend(ts.tools.keys())

    return {
        "agent_name": agent.name,
        "system_prompt": agent._instructions,
        "provider": agent.model.system,
        "model": agent.model.model_name,
        "tools": tools,
        "messages": ModelMessagesTypeAdapter.dump_python(messages),
        "usage": UsageTypeAdapter.dump_python(usage),
        "output": output,
    }


def _calc_cost(
    provider: str | None,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> dict[str, float | None]:
    """Calculate cost using genai_prices library."""
    if not provider or not model:
        return {"input_cost": None, "output_cost": None, "total_cost": None}

    try:
        token_usage = Usage(
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
        )
        price_data = calc_price(token_usage, provider_id=provider, model_ref=model)
        return {
            "input_cost": float(price_data.input_price),
            "output_cost": float(price_data.output_price),
            "total_cost": float(price_data.total_price),
        }
    except Exception as e:
        logger.warning(f"Cost calculation failed: {e}")
        return {"input_cost": None, "output_cost": None, "total_cost": None}


def _extract_answer_text(output: Any) -> str | None:
    """Extract answer text from agent output."""
    if isinstance(output, dict):
        return output.get("answer") or str(output)
    return str(output) if output else None


def _normalize_instructions(instructions: Any) -> str | None:
    """Convert instructions to string format."""
    if instructions is None:
        return None
    if isinstance(instructions, list):
        return "\n".join(str(item) for item in instructions)
    return str(instructions)


async def log_agent_run(
    agent: Agent,
    result: StreamedRunResult,
    question: str,
) -> int | None:
    """
    Log agent run to database.

    Args:
        agent: The agent instance
        result: Streamed run result
        question: The user's question

    Returns:
        Log ID if successful, None otherwise
    """
    try:
        output = result.output
        usage = result.usage()
        messages = result.all_messages()
        log_entry = _create_log_entry(agent, messages, usage, output)

        costs = _calc_cost(
            log_entry.get("provider"),
            log_entry.get("model"),
            usage.input_tokens,
            usage.output_tokens,
        )

        log_data = LogCreate(
            agent_name=log_entry.get("agent_name"),
            provider=log_entry.get("provider"),
            model=log_entry.get("model"),
            user_prompt=question,
            instructions=_normalize_instructions(log_entry.get("system_prompt")),
            total_input_tokens=usage.input_tokens,
            total_output_tokens=usage.output_tokens,
            assistant_answer=_extract_answer_text(output),
            raw_json=json.dumps(log_entry, default=str),
            **costs,
        )

        with get_db() as db:
            if not db:
                logger.warning("Database not available, skipping log save")
                return None

            log_id = insert_log(db, **log_data.model_dump())
            if log_id:
                logger.info(f"✅ Log saved to database with ID: {log_id}")
            return log_id

    except Exception as e:
        logger.error(f"Failed to save log to database: {e}", exc_info=True)
        return None


async def _log_agent_run_with_error_handling(
    agent: Agent,
    result: StreamedRunResult,
    question: str,
) -> None:
    """Wrapper that handles errors for background logging task."""
    try:
        await log_agent_run(agent, result, question)
    except Exception as e:
        logger.error(f"Background logging task failed: {e}", exc_info=True)


def log_agent_run_async(
    agent: Agent,
    result: StreamedRunResult,
    question: str,
) -> None:
    """
    Log agent run to database asynchronously (non-blocking).

    This function creates a background task to log the agent run without blocking
    the main execution flow. Errors are logged but don't affect the caller.

    Args:
        agent: The agent instance
        result: Streamed run result
        question: The user's question
    """
    try:
        # Create background task - don't await it
        asyncio.create_task(_log_agent_run_with_error_handling(agent, result, question))
    except Exception as e:
        # If we can't even create the task, log it but don't raise
        logger.warning(f"Failed to create background logging task: {e}")
