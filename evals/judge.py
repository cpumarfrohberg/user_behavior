"""LLM-as-a-Judge for evaluating agent answers"""

import asyncio
import json
import logging
from typing import Optional

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
)
from config.instructions import InstructionsConfig, InstructionType
from rag_agent.models import JudgeEvaluation, JudgeResult, RAGAnswer, TokenUsage

logger = logging.getLogger(__name__)

BACKOFF_BASE = 2  # Exponential backoff base for retry logic
FALLBACK_SCORE = 0.0  # Score to use when judge evaluation fails
ZERO_TOKENS = 0  # Zero token count for fallback cases
JSON_INDENT = 2  # Indentation for JSON formatting in tool calls
MAX_QUESTION_LOG_LENGTH = 50  # Max length for question in logs
SCORE_DECIMAL_PLACES = 2  # Decimal places for score formatting
DEFAULT_MAX_RETRIES = 3  # Default number of retry attempts


async def _run_judge_with_retry(
    judge_agent: Agent,
    prompt: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> JudgeResult:
    """
    Run judge with exponential backoff retry logic.

    Args:
        judge_agent: The judge agent instance
        prompt: The evaluation prompt
        max_retries: Maximum number of retry attempts (default: DEFAULT_MAX_RETRIES)

    Returns:
        JudgeResult containing evaluation and usage
    """
    for attempt in range(max_retries):
        try:
            result = await judge_agent.run(prompt)
            evaluation = result.output
            usage_obj = result.usage()
            usage = TokenUsage(
                input_tokens=usage_obj.input_tokens,
                output_tokens=usage_obj.output_tokens,
                total_tokens=usage_obj.input_tokens + usage_obj.output_tokens,
            )

            return JudgeResult(evaluation=evaluation, usage=usage)
        except Exception as e:
            if attempt == max_retries - 1:
                # Last attempt failed - return fallback
                logger.error(
                    f"Judge evaluation failed after {max_retries} attempts: {e}"
                )
                fallback_eval = JudgeEvaluation(
                    overall_score=FALLBACK_SCORE,
                    accuracy=FALLBACK_SCORE,
                    completeness=FALLBACK_SCORE,
                    relevance=FALLBACK_SCORE,
                    reasoning=f"Judge evaluation failed: {str(e)}",
                )
                return JudgeResult(
                    evaluation=fallback_eval,
                    usage=TokenUsage(
                        input_tokens=ZERO_TOKENS,
                        output_tokens=ZERO_TOKENS,
                        total_tokens=ZERO_TOKENS,
                    ),
                )

            # Exponential backoff: 1s, 2s, 4s
            wait_time = BACKOFF_BASE**attempt
            logger.warning(
                f"Judge evaluation attempt {attempt + 1} failed, retrying in {wait_time}s: {e}"
            )
            await asyncio.sleep(wait_time)

    # Should never reach here, but just in case
    raise RuntimeError("Judge evaluation failed after all retries")


async def evaluate_answer(
    question: str,
    answer: RAGAnswer,
    tool_calls: Optional[list[dict]] = None,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> JudgeResult:
    """
    Evaluate answer quality using LLM-as-a-Judge.

    Args:
        question: The original question asked
        answer: The RAGAnswer from the agent
        tool_calls: Optional list of tool calls made by the agent (for context)
        judge_model: Model to use for judging (default: DEFAULT_JUDGE_MODEL)
        max_retries: Maximum number of retry attempts (default: DEFAULT_MAX_RETRIES)

    Returns:
        JudgeResult containing evaluation and usage
    """
    instructions = InstructionsConfig.INSTRUCTIONS[InstructionType.JUDGE]

    model = OpenAIChatModel(
        model_name=judge_model,
        provider=OpenAIProvider(),
    )
    logger.info(f"Using judge model: {judge_model}")

    judge_agent = Agent(
        name="judge",
        model=model,
        instructions=instructions,
        output_type=JudgeEvaluation,
        model_settings=ModelSettings(
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_JUDGE_TEMPERATURE,
        ),
    )

    # Build tool calls section
    tool_calls_section = ""
    if tool_calls:
        tool_calls_section = f"""
<TOOL_CALLS>
{json.dumps(tool_calls, indent=JSON_INDENT)}
</TOOL_CALLS>"""

    # Prepare evaluation prompt with XML tags (best practice from Evidently AI)
    evaluation_prompt = f"""<QUESTION>{question}</QUESTION>

<ANSWER>{answer.answer}</ANSWER>

<SOURCES>{', '.join(answer.sources_used) if answer.sources_used else 'None'}</SOURCES>{tool_calls_section}

Evaluate this answer on accuracy, completeness, and relevance to the question."""

    logger.info(
        f"Evaluating answer for question: {question[:MAX_QUESTION_LOG_LENGTH]}..."
    )
    print("⚖️  Judge is evaluating the answer...")

    # Run judge evaluation with retry logic
    result = await _run_judge_with_retry(judge_agent, evaluation_prompt, max_retries)

    score_format = f".{SCORE_DECIMAL_PLACES}f"
    logger.info(
        f"Judge evaluation complete. Overall score: {result.evaluation.overall_score:{score_format}}, "
        f"Tokens: {result.usage.total_tokens}"
    )
    print(
        f"✅ Judge evaluation complete. Overall score: {result.evaluation.overall_score:{score_format}}"
    )

    return result
