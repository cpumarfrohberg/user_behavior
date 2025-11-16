"""Main evaluation runner for agents"""

import json
import logging
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from evals.combined_score import calculate_combined_score
from evals.judge import evaluate_answer
from evals.save_results import save_evaluation_results
from evals.source_metrics import calculate_hit_rate, calculate_mrr
from mongodb_agent.models import SearchAgentResult, SearchAnswer, TokenUsage

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "evals/results/evaluation.json"
QUESTION_PREVIEW_LENGTH = 50  # Max length for question in logs
SCORE_DECIMAL_PLACES = 2  # Decimal places for score formatting
FALLBACK_HIT_RATE = 0.0  # Fallback hit rate for failed evaluations
FALLBACK_MRR = 0.0  # Fallback MRR for failed evaluations
FALLBACK_JUDGE_SCORE = 0.0  # Fallback judge score for failed evaluations
FALLBACK_NUM_TOKENS = 0  # Fallback token count for failed evaluations
FALLBACK_COMBINED_SCORE = 0.0  # Fallback combined score for failed evaluations


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
    # Load ground truth
    ground_truth_path = Path(ground_truth_path)
    if not ground_truth_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {ground_truth_path}")

    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)

    original_count = len(ground_truth)

    # Sample if max_samples is provided
    if max_samples is not None and max_samples < original_count:
        ground_truth = random.sample(ground_truth, max_samples)
        logger.info(
            f"Loaded {original_count} questions from ground truth, "
            f"sampling {max_samples} questions for evaluation"
        )
    else:
        logger.info(f"Loaded {original_count} questions from ground truth")

    results = []

    # Evaluate each question
    for i, item in enumerate(ground_truth, 1):
        question = item["question"]
        expected_sources = item.get("expected_sources", [])

        logger.info(
            f"Evaluating question {i}/{len(ground_truth)}: {question[:QUESTION_PREVIEW_LENGTH]}..."
        )

        try:
            # Run agent query
            result = await agent_query_fn(question)

            # Calculate source metrics
            actual_sources = result.answer.sources_used or []
            hit_rate = calculate_hit_rate(expected_sources, actual_sources)
            mrr = calculate_mrr(expected_sources, actual_sources)

            # Run judge evaluation
            judge_result = await evaluate_answer(
                question,
                result.answer,
                tool_calls=result.tool_calls,
                expected_sources=expected_sources,
                judge_model=judge_model,
            )
            judge_score = judge_result.evaluation.overall_score

            # Count tokens (agent + judge)
            # Note: Current agents don't track usage yet, so we'll use judge tokens only
            # This will be updated when agents return TokenUsage
            agent_tokens = 0  # TODO: Get from agent when available
            judge_tokens = judge_result.usage.total_tokens
            total_tokens = agent_tokens + judge_tokens

            # Calculate combined score
            combined_score = calculate_combined_score(
                hit_rate=hit_rate,
                judge_score=judge_score,
                num_tokens=total_tokens,
            )

            # Store result
            results.append(
                {
                    "question": question,
                    "hit_rate": hit_rate,
                    "mrr": mrr,
                    "judge_score": judge_score,
                    "num_tokens": total_tokens,
                    "combined_score": combined_score,
                }
            )

            score_format = f".{SCORE_DECIMAL_PLACES}f"
            logger.info(
                f"Question {i} complete: hit_rate={hit_rate:{score_format}}, "
                f"mrr={mrr:{score_format}}, judge_score={judge_score:{score_format}}, "
                f"combined_score={combined_score:{score_format}}"
            )

        except Exception as e:
            logger.error(f"Error evaluating question {i}: {e}")
            # Store failed result with fallback values
            results.append(
                {
                    "question": question,
                    "hit_rate": FALLBACK_HIT_RATE,
                    "mrr": FALLBACK_MRR,
                    "judge_score": FALLBACK_JUDGE_SCORE,
                    "num_tokens": FALLBACK_NUM_TOKENS,
                    "combined_score": FALLBACK_COMBINED_SCORE,
                }
            )

    # Prepare metadata
    metadata: dict[str, Any] = {
        "ground_truth_file": str(ground_truth_path),
        "total_questions_in_ground_truth": original_count,
    }
    if judge_model:
        metadata["judge_model"] = judge_model
    if max_samples is not None:
        metadata["max_samples"] = max_samples
        metadata["sampled"] = True

    # Save results
    output_path = save_evaluation_results(results, output_path, metadata)

    logger.info(f"Evaluation complete. Results saved to: {output_path}")

    return output_path
