import asyncio
import json
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

import typer

from config import (
    DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH,
    DEFAULT_GROUND_TRUTH_OUTPUT,
    DEFAULT_GROUND_TRUTH_SAMPLES,
    DEFAULT_JUDGE_MODEL,
    MONGODB_COLLECTION,
    MONGODB_DB,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
)
from cypher_agent.agent import CypherQueryAgent
from cypher_agent.config import CypherAgentConfig
from cypher_agent.tools import initialize_neo4j_driver
from evals.evaluate import (
    DEFAULT_OUTPUT_PATH,
    evaluate_agent,
)
from evals.evaluate import (
    evaluate_cypher_agent as run_cypher_evaluation,
)
from evals.generate_ground_truth import (
    generate_ground_truth_from_mongodb,
    save_ground_truth,
)
from mongodb_agent.agent import MongoDBSearchAgent
from mongodb_agent.config import MongoDBConfig
from stream_stackexchange.collector import collect_and_store

app = typer.Typer()

EXIT_CODE_ERROR = 1
MAX_SOURCES_DISPLAY = 10
SEPARATOR_WIDTH = 60
MAX_DETAILED_RESULTS = 5
QUESTION_PREVIEW_LENGTH = 50
QUERY_PREVIEW_LENGTH = 50
DEFAULT_PAGES = 5
DEFAULT_MAX_SAMPLES = 15
DEFAULT_NUM_QUESTIONS = 0
DEFAULT_SCORE = 0.0


def _handle_error(e: Exception, verbose: bool = False) -> None:
    typer.echo(f"Error: {str(e)}", err=True)
    if verbose:
        typer.echo(traceback.format_exc(), err=True)
    raise typer.Exit(EXIT_CODE_ERROR)


def _run_async(coro: Callable, verbose: bool = False) -> Any:
    try:
        return asyncio.run(coro())
    except Exception as e:
        _handle_error(e, verbose)


def _init_mongodb_agent() -> MongoDBSearchAgent:
    config = MongoDBConfig()
    config.collection = "questions"
    agent = MongoDBSearchAgent(config)
    agent.initialize()
    return agent


def _init_cypher_agent() -> CypherQueryAgent:
    initialize_neo4j_driver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    config = CypherAgentConfig()
    agent = CypherQueryAgent(config)
    agent.initialize()
    return agent


def _print_answer(result: Any, question: str, verbose: bool = False) -> None:
    typer.echo(f"\nQuestion: {question}")
    typer.echo(f"Answer: {result.answer.answer}")
    typer.echo(f"Confidence: {result.answer.confidence:.2f}")

    if hasattr(result.answer, "agents_used"):
        typer.echo(f"Agents: {', '.join(result.answer.agents_used)}")
    else:
        typer.echo(f"Tool Calls: {len(result.tool_calls)}")

    if verbose:
        if hasattr(result.answer, "agents_used"):
            typer.echo(f"Reasoning: {result.answer.reasoning}")
        else:
            for i, call in enumerate(result.tool_calls, 1):
                typer.echo(f"  {i}. {call['tool_name']}: {call['args']}")
            if result.answer.reasoning:
                typer.echo(f"Reasoning: {result.answer.reasoning}")

    if result.answer.sources_used:
        typer.echo("Sources:")
        for source in result.answer.sources_used[:MAX_SOURCES_DISPLAY]:
            typer.echo(f"  - {source}")


def _print_evaluation_summary(
    results_data: dict[str, Any], verbose: bool = False
) -> None:
    summary = results_data.get("summary", {})
    typer.echo("\n" + "=" * SEPARATOR_WIDTH)
    typer.echo("EVALUATION SUMMARY")
    typer.echo("=" * SEPARATOR_WIDTH)
    typer.echo(f"Questions: {results_data.get('num_questions', DEFAULT_NUM_QUESTIONS)}")
    typer.echo(f"Hit Rate: {summary.get('avg_hit_rate', DEFAULT_SCORE):.2f}")
    typer.echo(f"MRR: {summary.get('avg_mrr', DEFAULT_SCORE):.2f}")
    typer.echo(f"Judge Score: {summary.get('avg_judge_score', DEFAULT_SCORE):.2f}")
    typer.echo(
        f"Combined Score: {summary.get('avg_combined_score', DEFAULT_SCORE):.2f}"
    )
    typer.echo(f"Total Tokens: {summary.get('total_tokens', DEFAULT_NUM_QUESTIONS):,}")
    typer.echo(f"Results: {results_data.get('output_file', 'N/A')}")
    typer.echo("=" * SEPARATOR_WIDTH)

    if verbose:
        typer.echo("\nDetailed results:")
        for i, result in enumerate(
            results_data.get("results", [])[:MAX_DETAILED_RESULTS], 1
        ):
            typer.echo(
                f"\n  {i}. {result.get('question', 'N/A')[:QUESTION_PREVIEW_LENGTH]}..."
            )
            typer.echo(f"     Hit Rate: {result.get('hit_rate', DEFAULT_SCORE):.2f}")
            typer.echo(f"     MRR: {result.get('mrr', DEFAULT_SCORE):.2f}")
            typer.echo(f"     Judge: {result.get('judge_score', DEFAULT_SCORE):.2f}")
            typer.echo(
                f"     Combined: {result.get('combined_score', DEFAULT_SCORE):.2f}"
            )
            if result.get("query_used"):
                query = result["query_used"]
                typer.echo(
                    f"     Query: {query[:QUERY_PREVIEW_LENGTH]}{'...' if len(query) > QUERY_PREVIEW_LENGTH else ''}"
                )


def _run_evaluation(
    ground_truth_path: Path,
    agent_query_fn: Callable[[str], Any],
    evaluation_fn: Callable,
    output: str,
    judge_model: str | None,
    max_samples: int | None,
    verbose: bool,
) -> None:
    if not ground_truth_path.exists():
        typer.echo(f"Error: Ground truth file not found: {ground_truth_path}", err=True)
        raise typer.Exit(EXIT_CODE_ERROR)

    with open(ground_truth_path, "r") as f:
        total_questions = len(json.load(f))

    num_to_evaluate = (
        max_samples if max_samples and max_samples > 0 else total_questions
    )
    if verbose:
        typer.echo(f"Loaded {total_questions} questions, evaluating {num_to_evaluate}")

    async def execute():
        result_path = await evaluation_fn(
            ground_truth_path=ground_truth_path,
            agent_query_fn=agent_query_fn,
            output_path=output,
            judge_model=judge_model or DEFAULT_JUDGE_MODEL,
            max_samples=max_samples if max_samples and max_samples > 0 else None,
        )

        with open(result_path, "r") as f:
            results_data = json.load(f)
        results_data["output_file"] = str(result_path)
        _print_evaluation_summary(results_data, verbose)
        return result_path

    _run_async(execute, verbose)


@app.command()
def collect(
    pages: int = typer.Option(DEFAULT_PAGES, "--pages", "-p"),
    site: str = typer.Option(None, "--site", "-s"),
    tag: str = typer.Option(None, "--tag", "-t"),
):
    """Collect questions from StackExchange API"""
    try:
        total_stored = collect_and_store(site=site, tag=tag, pages=pages)
        typer.echo(f"Collected {total_stored} questions")
    except Exception as e:
        _handle_error(e)


@app.command()
def agent_ask(
    question: str = typer.Argument(...),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Ask a question using the MongoDB agent"""
    try:
        agent = _init_mongodb_agent()

        async def run():
            result = await agent.query(question)
            _print_answer(result, question, verbose)

        _run_async(run, verbose)
    except Exception as e:
        _handle_error(e, verbose)


@app.command()
def orchestrator_ask(
    question: str = typer.Argument(...),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Ask a question using the Orchestrator Agent"""
    from orchestrator.agent import OrchestratorAgent
    from orchestrator.config import OrchestratorConfig
    from orchestrator.tools import initialize_mongodb_agent

    try:
        mongodb_config = MongoDBConfig()
        mongodb_config.collection = "questions"
        initialize_mongodb_agent(mongodb_config)

        orchestrator = OrchestratorAgent(OrchestratorConfig())
        orchestrator.initialize()

        async def run():
            result = await orchestrator.query(question)
            result_wrapper = type(
                "Result", (), {"answer": result.answer, "tool_calls": []}
            )()
            _print_answer(result_wrapper, question, verbose)
            if verbose:
                typer.echo(
                    f"\nTokens: {result.token_usage.total_tokens} "
                    f"({result.token_usage.input_tokens} in, {result.token_usage.output_tokens} out)"
                )

        _run_async(run, verbose)
    except Exception as e:
        _handle_error(e, verbose)


@app.command()
def generate_ground_truth(
    samples: int = typer.Option(DEFAULT_GROUND_TRUTH_SAMPLES, "--samples", "-n"),
    output: str = typer.Option(DEFAULT_GROUND_TRUTH_OUTPUT, "--output", "-o"),
    min_title_length: int = typer.Option(
        DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH, "--min-title-length", "-m"
    ),
):
    """Generate ground truth dataset"""
    try:
        ground_truth = generate_ground_truth_from_mongodb(
            n_samples=samples,
            min_title_length=min_title_length,
        )

        if not ground_truth:
            typer.echo("Error: No ground truth data generated", err=True)
            raise typer.Exit(EXIT_CODE_ERROR)

        save_ground_truth(ground_truth, output)
        output_path = Path(output).with_suffix(".json")
        typer.echo(f"Generated {len(ground_truth)} examples: {output_path}")
    except Exception as e:
        _handle_error(e)


@app.command()
def evaluate(
    ground_truth: str = typer.Option(
        DEFAULT_GROUND_TRUTH_OUTPUT, "--ground-truth", "-g"
    ),
    output: str = typer.Option(DEFAULT_OUTPUT_PATH, "--output", "-o"),
    judge_model: str = typer.Option(None, "--judge-model", "-j"),
    max_samples: int = typer.Option(DEFAULT_MAX_SAMPLES, "--max-samples", "-n"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Evaluate MongoDB agent"""
    try:
        agent = _init_mongodb_agent()
        _run_evaluation(
            ground_truth_path=Path(ground_truth),
            agent_query_fn=lambda q: agent.query(q),
            evaluation_fn=evaluate_agent,
            output=output,
            judge_model=judge_model,
            max_samples=max_samples,
            verbose=verbose,
        )
    except Exception as e:
        _handle_error(e, verbose)


@app.command()
def evaluate_cypher_agent(
    ground_truth: str = typer.Option(
        "evals/cypher_ground_truth.json", "--ground-truth", "-g"
    ),
    output: str = typer.Option(
        "evals/results/cypher_evaluation.json", "--output", "-o"
    ),
    judge_model: str = typer.Option(None, "--judge-model", "-j"),
    max_samples: int = typer.Option(DEFAULT_MAX_SAMPLES, "--max-samples", "-n"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Evaluate Cypher query agent"""
    try:
        agent = _init_cypher_agent()
        _run_evaluation(
            ground_truth_path=Path(ground_truth),
            agent_query_fn=lambda q: agent.query(q),
            evaluation_fn=run_cypher_evaluation,
            output=output,
            judge_model=judge_model,
            max_samples=max_samples,
            verbose=verbose,
        )
    except Exception as e:
        _handle_error(e, verbose)


@app.command()
def test(
    path: str = typer.Option("tests", "--path", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    markers: str = typer.Option(None, "--markers", "-m"),
    coverage: bool = typer.Option(False, "--coverage", "-c"),
):
    """Run tests using pytest"""
    try:
        cmd = ["uv", "run", "pytest", path, "-v" if verbose else "-q"]
        if markers:
            cmd.extend(["-m", markers])
        if coverage:
            cmd.extend(["--cov", ".", "--cov-report", "term-missing"])

        result = subprocess.run(cmd, cwd=Path.cwd())
        if result.returncode != 0:
            sys.exit(result.returncode)
    except Exception as e:
        _handle_error(e, verbose)


if __name__ == "__main__":
    app()
