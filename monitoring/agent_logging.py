import json
import logging
from typing import Any

import pydantic
from genai_prices import Usage, calc_price
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.result import StreamedRunResult
from pydantic_ai.usage import RunUsage

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
) -> tuple[float | None, float | None, float | None]:
    """Calculate cost using genai_prices library. Returns (input_cost, output_cost, total_cost)."""
    if not provider or not model:
        return (None, None, None)

    try:
        token_usage = Usage(
            input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0)
        )
        price_data = calc_price(token_usage, provider_id=provider, model_ref=model)
        return (
            float(price_data.input_price),
            float(price_data.output_price),
            float(price_data.total_price),
        )
    except Exception as e:
        logger.warning(f"Cost calculation failed: {e}")
        return (None, None, None)


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
        from monitoring.db import get_db, insert_log
        from monitoring.schemas import LogCreate

        # Extract data from agent run
        output = result.output
        usage = result.usage()
        messages = result.all_messages()
        log_entry = _create_log_entry(agent, messages, usage, output)

        # Extract answer text
        answer_text = None
        if isinstance(output, dict):
            answer_text = output.get("answer", str(output))
        elif output:
            answer_text = str(output)

        # Calculate costs
        input_cost, output_cost, total_cost = _calc_cost(
            log_entry["provider"],
            log_entry["model"],
            usage.input_tokens,
            usage.output_tokens,
        )

        # Convert instructions to string
        instructions_text = log_entry["system_prompt"]
        if isinstance(instructions_text, list):
            instructions_text = "\n".join(str(item) for item in instructions_text)
        elif instructions_text is not None:
            instructions_text = str(instructions_text)

        # Validate and save
        log_data = LogCreate(
            agent_name=log_entry["agent_name"],
            provider=log_entry["provider"],
            model=log_entry["model"],
            user_prompt=question,
            instructions=instructions_text,
            total_input_tokens=usage.input_tokens,
            total_output_tokens=usage.output_tokens,
            assistant_answer=answer_text,
            raw_json=json.dumps(log_entry, default=str),
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
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
