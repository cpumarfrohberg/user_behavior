"""Main evaluation runner for agents"""

import json
import logging
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from cypher_agent.models import CypherAgentResult, CypherAnswer
from evals.combined_score import calculate_combined_score
from evals.judge import evaluate_answer, evaluate_orchestrator_answer
from evals.save_results import save_evaluation_results
from evals.source_metrics import calculate_hit_rate, calculate_mrr
from mongodb_agent.models import SearchAgentResult, SearchAnswer, TokenUsage
from orchestrator.models import OrchestratorAgentResult

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "evals/results/evaluation.json"
QUESTION_PREVIEW_LENGTH = 50  # Max length for question in logs
SCORE_DECIMAL_PLACES = 2  # Decimal places for score formatting
FALLBACK_HIT_RATE = 0.0  # Fallback hit rate for failed evaluations
FALLBACK_MRR = 0.0  # Fallback MRR for failed evaluations
FALLBACK_JUDGE_SCORE = 0.0  # Fallback judge score for failed evaluations
FALLBACK_NUM_TOKENS = 0  # Fallback token count for failed evaluations
FALLBACK_COMBINED_SCORE = 0.0  # Fallback combined score for failed evaluations


def _load_ground_truth(ground_truth_path: Path) -> list[dict[str, Any]]:
    if not ground_truth_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {ground_truth_path}")
    with open(ground_truth_path, "r") as f:
        return json.load(f)


def _sample_ground_truth(
    ground_truth: list[dict[str, Any]], max_samples: int | None
) -> tuple[list[dict[str, Any]], int]:
    """Sample ground truth if max_samples is provided."""
    original_count = len(ground_truth)
    if max_samples is not None and max_samples < original_count:
        sampled = random.sample(ground_truth, max_samples)
        logger.info(
            f"Loaded {original_count} questions from ground truth, "
            f"sampling {max_samples} questions for evaluation"
        )
        return sampled, original_count
    logger.info(f"Loaded {original_count} questions from ground truth")
    return ground_truth, original_count


def _calculate_source_metrics(
    expected_sources: list[str], actual_sources: list[str]
) -> tuple[float, float]:
    hit_rate = calculate_hit_rate(expected_sources, actual_sources)
    mrr = calculate_mrr(expected_sources, actual_sources)
    return hit_rate, mrr


def _calculate_token_usage(result: Any, judge_result: Any) -> int:
    agent_tokens = (
        result.token_usage.total_tokens if hasattr(result, "token_usage") else 0
    )
    judge_tokens = judge_result.usage.total_tokens
    return agent_tokens + judge_tokens


def _build_evaluation_result(
    question: str,
    hit_rate: float,
    mrr: float,
    judge_score: float,
    total_tokens: int,
    combined_score: float,
    extra_fields: dict[str, Any],
) -> dict[str, Any]:
    """Build a single evaluation result dictionary."""
    result = {
        "question": question,
        "hit_rate": hit_rate,
        "mrr": mrr,
        "judge_score": judge_score,
        "num_tokens": total_tokens,
        "combined_score": combined_score,
    }
    result.update(extra_fields)
    return result


def _build_fallback_result(
    question: str, extra_fields: dict[str, Any]
) -> dict[str, Any]:
    result = {
        "question": question,
        "hit_rate": FALLBACK_HIT_RATE,
        "mrr": FALLBACK_MRR,
        "judge_score": FALLBACK_JUDGE_SCORE,
        "num_tokens": FALLBACK_NUM_TOKENS,
        "combined_score": FALLBACK_COMBINED_SCORE,
    }
    result.update(extra_fields)
    return result


def _format_extra_fields_for_logging(extra_fields: dict[str, Any]) -> str:
    parts = []
    for k, v in extra_fields.items():
        if k == "query_used" and isinstance(v, str) and len(v) > 50:
            parts.append(f"{k}={v[:50]}...")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts) if parts else ""


def _log_evaluation_result(
    question_num: int,
    total_questions: int,
    hit_rate: float,
    mrr: float,
    judge_score: float,
    combined_score: float,
    extra_fields: dict[str, Any],
) -> None:
    """Log the result of a single question evaluation."""
    score_format = f".{SCORE_DECIMAL_PLACES}f"
    extra_info = _format_extra_fields_for_logging(extra_fields)
    logger.info(
        f"Question {question_num} complete: hit_rate={hit_rate:{score_format}}, "
        f"mrr={mrr:{score_format}}, judge_score={judge_score:{score_format}}, "
        f"combined_score={combined_score:{score_format}}"
        + (f", {extra_info}" if extra_info else "")
    )


async def _evaluate_single_question(
    question: str,
    expected_sources: list[str],
    agent_query_fn: Callable[[str], Awaitable[Any]],
    judge_fn: Callable[
        [str, Any, list[dict] | None, list[str], str | None], Awaitable[Any]
    ],
    extract_extra_fields: Callable[[Any], dict[str, Any]],
    judge_model: str | None,
) -> dict[str, Any]:
    result = await agent_query_fn(question)

    actual_sources = result.answer.sources_used or []
    hit_rate, mrr = _calculate_source_metrics(expected_sources, actual_sources)

    tool_calls = getattr(result, "tool_calls", None)
    judge_result = await judge_fn(
        question,
        result.answer,
        tool_calls,
        expected_sources,
        judge_model,
    )
    judge_score = judge_result.evaluation.overall_score

    total_tokens = _calculate_token_usage(result, judge_result)
    combined_score = calculate_combined_score(
        hit_rate=hit_rate,
        judge_score=judge_score,
        num_tokens=total_tokens,
    )

    extra_fields = extract_extra_fields(result)
    return _build_evaluation_result(
        question=question,
        hit_rate=hit_rate,
        mrr=mrr,
        judge_score=judge_score,
        total_tokens=total_tokens,
        combined_score=combined_score,
        extra_fields=extra_fields,
    )


def _build_metadata(
    ground_truth_path: Path,
    original_count: int,
    agent_type: str | None,
    judge_model: str | None,
    max_samples: int | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "ground_truth_file": str(ground_truth_path),
        "total_questions_in_ground_truth": original_count,
    }
    if agent_type:
        metadata["agent_type"] = agent_type
    if judge_model:
        metadata["judge_model"] = judge_model
    if max_samples is not None:
        metadata["max_samples"] = max_samples
        metadata["sampled"] = True
    return metadata


async def _evaluate_agent_generic(
    ground_truth_path: Path,
    agent_query_fn: Callable[[str], Awaitable[Any]],
    judge_fn: Callable[
        [str, Any, list[dict] | None, list[str], str | None], Awaitable[Any]
    ],
    extract_extra_fields: Callable[[Any], dict[str, Any]],
    agent_type: str | None = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    judge_model: str | None = None,
    max_samples: int | None = None,
) -> Path:
    """
    Generic evaluation workflow for any agent type.

    Args:
        ground_truth_path: Path to ground truth JSON file
        agent_query_fn: Async function that takes a question and returns an agent result
        judge_fn: Async function to evaluate the answer (takes question, answer, tool_calls, expected_sources, judge_model)
        extract_extra_fields: Function to extract agent-specific fields from result (returns dict)
        agent_type: Type of agent for metadata (e.g., "cypher", "orchestrator")
        output_path: Path to output JSON file
        judge_model: Model to use for judging
        max_samples: Maximum number of questions to evaluate (None = evaluate all)

    Returns:
        Path to saved JSON file
    """
    ground_truth = _load_ground_truth(ground_truth_path)
    ground_truth, original_count = _sample_ground_truth(ground_truth, max_samples)

    results = []

    for i, item in enumerate(ground_truth, 1):
        question = item["question"]
        expected_sources = item.get("expected_sources", [])

        logger.info(
            f"Evaluating question {i}/{len(ground_truth)}: {question[:QUESTION_PREVIEW_LENGTH]}..."
        )

        try:
            result = await _evaluate_single_question(
                question=question,
                expected_sources=expected_sources,
                agent_query_fn=agent_query_fn,
                judge_fn=judge_fn,
                extract_extra_fields=extract_extra_fields,
                judge_model=judge_model,
            )
            results.append(result)

            _log_evaluation_result(
                question_num=i,
                total_questions=len(ground_truth),
                hit_rate=result["hit_rate"],
                mrr=result["mrr"],
                judge_score=result["judge_score"],
                combined_score=result["combined_score"],
                extra_fields={
                    k: v
                    for k, v in result.items()
                    if k
                    not in {
                        "question",
                        "hit_rate",
                        "mrr",
                        "judge_score",
                        "num_tokens",
                        "combined_score",
                    }
                },
            )

        except Exception as e:
            logger.error(f"Error evaluating question {i}: {e}")
            fallback_result = _build_fallback_result(
                question=question,
                extra_fields=extract_extra_fields(None),
            )
            results.append(fallback_result)

    metadata = _build_metadata(
        ground_truth_path=ground_truth_path,
        original_count=original_count,
        agent_type=agent_type,
        judge_model=judge_model,
        max_samples=max_samples,
    )

    output_path = save_evaluation_results(results, output_path, metadata)

    agent_name = agent_type or "agent"
    logger.info(
        f"{agent_name.capitalize()} evaluation complete. Results saved to: {output_path}"
    )

    return output_path


async def evaluate_agent(
    ground_truth_path: str | Path,
    agent_query_fn: Callable[[str], Awaitable[SearchAgentResult]],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    judge_model: str | None = None,
    max_samples: int | None = None,
) -> Path:
    """
    Run full evaluation workflow on an agent.

    Args:
        ground_truth_path: Path to ground truth JSON file
        agent_query_fn: Async function that takes a question and returns SearchAgentResult
                       The function should return SearchAgentResult with answer and tool_calls
        output_path: Path to output JSON file (default: DEFAULT_OUTPUT_PATH)
        judge_model: Model to use for judging (default: from config)
        max_samples: Maximum number of questions to evaluate (None = evaluate all).
                     If provided, a random sample will be selected.

    Returns:
        Path to saved JSON file

    Example:
        async def my_agent_query(question: str):
            # Your agent query logic
            return await agent.query(question)

        path = await evaluate_agent(
            "evals/ground_truth.json",
            my_agent_query,
            "evals/results/evaluation.json",
            max_samples=10,  # Evaluate only 10 random questions
        )
    """

    async def judge_wrapper(
        q: str, ans: Any, tc: list[dict] | None, es: list[str], jm: str | None
    ) -> Any:
        return await evaluate_answer(
            q, ans, tool_calls=tc, expected_sources=es, judge_model=jm
        )

    def extract_extra(_: Any) -> dict[str, Any]:
        return {}

    return await _evaluate_agent_generic(
        ground_truth_path=Path(ground_truth_path),
        agent_query_fn=agent_query_fn,
        judge_fn=judge_wrapper,
        extract_extra_fields=extract_extra,
        agent_type=None,
        output_path=output_path,
        judge_model=judge_model,
        max_samples=max_samples,
    )


async def evaluate_orchestrator_agent(
    ground_truth_path: str | Path,
    agent_query_fn: Callable[[str], Awaitable[OrchestratorAgentResult]],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    judge_model: str | None = None,
    max_samples: int | None = None,
) -> Path:
    """
    Run full evaluation workflow on an orchestrator agent.

    Args:
        ground_truth_path: Path to ground truth JSON file
        agent_query_fn: Async function that takes a question and returns OrchestratorAgentResult
                       The function should return OrchestratorAgentResult with answer and token_usage
        output_path: Path to output JSON file (default: DEFAULT_OUTPUT_PATH)
        judge_model: Model to use for judging (default: from config)
        max_samples: Maximum number of questions to evaluate (None = evaluate all).
                     If provided, a random sample will be selected.

    Returns:
        Path to saved JSON file

    Example:
        async def my_orchestrator_query(question: str):
            # Your orchestrator query logic
            return await orchestrator.query(question)

        path = await evaluate_orchestrator_agent(
            "evals/ground_truth.json",
            my_orchestrator_query,
            "evals/results/orchestrator_evaluation.json",
            max_samples=10,  # Evaluate only 10 random questions
        )
    """

    async def judge_wrapper(
        q: str, ans: Any, tc: list[dict] | None, es: list[str], jm: str | None
    ) -> Any:
        return await evaluate_orchestrator_answer(
            q, ans, tool_calls=None, expected_sources=es, judge_model=jm
        )

    def extract_extra(result: Any) -> dict[str, Any]:
        if result is None:
            return {"agents_used": []}
        return {
            "agents_used": result.answer.agents_used
            if hasattr(result, "answer")
            else []
        }

    return await _evaluate_agent_generic(
        ground_truth_path=Path(ground_truth_path),
        agent_query_fn=agent_query_fn,
        judge_fn=judge_wrapper,
        extract_extra_fields=extract_extra,
        agent_type="orchestrator",
        output_path=output_path,
        judge_model=judge_model,
        max_samples=max_samples,
    )


async def evaluate_cypher_agent(
    ground_truth_path: str | Path,
    agent_query_fn: Callable[[str], Awaitable[CypherAgentResult]],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    judge_model: str | None = None,
    max_samples: int | None = None,
) -> Path:
    """
    Run full evaluation workflow on a Cypher query agent.

    Args:
        ground_truth_path: Path to ground truth JSON file
        agent_query_fn: Async function that takes a question and returns CypherAgentResult
                       The function should return CypherAgentResult with answer and tool_calls
        output_path: Path to output JSON file (default: DEFAULT_OUTPUT_PATH)
        judge_model: Model to use for judging (default: from config)
        max_samples: Maximum number of questions to evaluate (None = evaluate all).
                     If provided, a random sample will be selected.

    Returns:
        Path to saved JSON file

    Example:
        async def my_cypher_query(question: str):
            # Your Cypher agent query logic
            return await cypher_agent.query(question)

        path = await evaluate_cypher_agent(
            "evals/cypher_ground_truth.json",
            my_cypher_query,
            "evals/results/cypher_evaluation.json",
            max_samples=10,  # Evaluate only 10 random questions
        )
    """

    async def judge_wrapper(
        q: str, ans: Any, tc: list[dict] | None, es: list[str], jm: str | None
    ) -> Any:
        return await evaluate_answer(
            q,
            cast(SearchAnswer, ans),
            tool_calls=tc,
            expected_sources=es,
            judge_model=jm,
        )

    def extract_extra(result: Any) -> dict[str, Any]:
        if result is None:
            return {"query_used": ""}
        if hasattr(result, "answer") and hasattr(result.answer, "query_used"):
            return {"query_used": result.answer.query_used}
        return {"query_used": ""}

    return await _evaluate_agent_generic(
        ground_truth_path=Path(ground_truth_path),
        agent_query_fn=agent_query_fn,
        judge_fn=judge_wrapper,
        extract_extra_fields=extract_extra,
        agent_type="cypher",
        output_path=output_path,
        judge_model=judge_model,
        max_samples=max_samples,
    )
