# CLI for User Behavior Analysis using StackExchange RAG

import asyncio
import json
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
)
from evals.evaluate import DEFAULT_OUTPUT_PATH, evaluate_agent
from evals.generate_ground_truth import (
    generate_ground_truth_from_mongodb,
    save_ground_truth,
)
from mongodb_agent.agent import MongoDBSearchAgent
from mongodb_agent.config import MongoDBConfig
from stream_stackexchange.collector import collect_and_store

app = typer.Typer()


def _handle_error(e: Exception, verbose: bool = False) -> None:
    """Handle errors with optional verbose traceback."""
    typer.echo(f"❌ Error: {str(e)}", err=True)
    if verbose:
        typer.echo(traceback.format_exc(), err=True)
    raise typer.Exit(1)


def _run_async(coro: Callable, verbose: bool = False) -> Any:
    """Run async function with error handling."""
    try:
        return asyncio.run(coro())
    except Exception as e:
        _handle_error(e, verbose)


def _init_mongodb_agent(verbose: bool = False) -> MongoDBSearchAgent:
    """Initialize MongoDB agent with standard config."""
    if verbose:
        typer.echo("📥 Initializing MongoDB Agent...")
    config = MongoDBConfig()
    config.collection = "questions"
    agent = MongoDBSearchAgent(config)
    agent.initialize()
    if verbose:
        typer.echo("✅ Agent initialized successfully!")
    return agent


def _print_answer(result: Any, question: str, verbose: bool = False) -> None:
    """Print agent answer with formatting."""
    typer.echo(f"\n❓ Question: {question}")
    typer.echo(f"💡 Answer: {result.answer.answer}")
    typer.echo(f"🎯 Confidence: {result.answer.confidence:.2f}")

    if hasattr(result.answer, "agents_used"):
        typer.echo(f"🤖 Agents Used: {', '.join(result.answer.agents_used)}")
    else:
        typer.echo(f"🔍 Tool Calls: {len(result.tool_calls)}")

    if verbose:
        if hasattr(result.answer, "agents_used"):
            typer.echo(f"\n💭 Routing Reasoning: {result.answer.reasoning}")
        else:
            typer.echo("\n📋 Tool Call History:")
            for i, call in enumerate(result.tool_calls, 1):
                typer.echo(f"  {i}. {call['tool_name']}: {call['args']}")
            if result.answer.reasoning:
                typer.echo(f"\n💭 Reasoning: {result.answer.reasoning}")

    if result.answer.sources_used:
        typer.echo("\n📚 Sources:")
        for i, source in enumerate(result.answer.sources_used[:10], 1):
            typer.echo(f"  {i}. {source}")


@app.command()
def collect(
    pages: int = typer.Option(
        5,
        "--pages",
        "-p",
        help="Number of pages to fetch (default: 5)",
    ),
    site: str = typer.Option(
        None,
        "--site",
        "-s",
        help="StackExchange site (default: from config)",
    ),
    tag: str = typer.Option(
        None,
        "--tag",
        "-t",
        help="Tag to filter by (default: from config)",
    ),
):
    """Collect questions from StackExchange API and store in MongoDB"""
    try:
        typer.echo("📥 Starting data collection from StackExchange...")
        total_stored = collect_and_store(site=site, tag=tag, pages=pages)
        typer.echo(
            f"\n✅ Collection complete: {total_stored} questions stored in MongoDB"
        )
    except Exception as e:
        _handle_error(e)


@app.command()
def agent_ask(
    question: str = typer.Argument(..., help="Question to ask the agent"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show tool calls"),
):
    """Ask a question using the MongoDB agent directly (makes multiple searches)"""
    try:
        agent = _init_mongodb_agent(verbose)
        typer.echo(
            "🤖 Running agent query"
            + ("..." if verbose else " (this may take a minute)...")
        )

        async def run_query():
            result = await agent.query(question)
            _print_answer(result, question, verbose)

        _run_async(run_query, verbose)
    except Exception as e:
        _handle_error(e, verbose)


@app.command()
def orchestrator_ask(
    question: str = typer.Argument(..., help="Question to ask"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Ask a question using the Orchestrator Agent (intelligently routes to RAG or Cypher Query Agent)"""
    from orchestrator.agent import OrchestratorAgent
    from orchestrator.config import OrchestratorConfig
    from orchestrator.tools import initialize_mongodb_agent

    try:
        if verbose:
            typer.echo("📥 Initializing Orchestrator Agent...")

        mongodb_config = MongoDBConfig()
        mongodb_config.collection = "questions"
        initialize_mongodb_agent(mongodb_config)

        orchestrator = OrchestratorAgent(OrchestratorConfig())
        orchestrator.initialize()

        typer.echo(
            "✅ Orchestrator initialized successfully!"
            if verbose
            else "🎯 Orchestrator is analyzing your question..."
        )

        async def run_query():
            answer = await orchestrator.query(question)
            # Wrap in result-like object for _print_answer
            result = type("Result", (), {"answer": answer, "tool_calls": []})()
            _print_answer(result, question, verbose)

        _run_async(run_query, verbose)
    except Exception as e:
        _handle_error(e, verbose)


@app.command()
def generate_ground_truth(
    samples: int = typer.Option(
        DEFAULT_GROUND_TRUTH_SAMPLES,
        "--samples",
        "-n",
        help="Number of samples to generate",
    ),
    output: str = typer.Option(
        DEFAULT_GROUND_TRUTH_OUTPUT,
        "--output",
        "-o",
        help="Output JSON file path",
    ),
    min_title_length: int = typer.Option(
        DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH,
        "--min-title-length",
        "-m",
        help="Minimum title length to include",
    ),
):
    """Generate ground truth dataset for evaluation"""
    try:
        typer.echo(f"📥 Connecting to MongoDB: {MONGODB_DB}.{MONGODB_COLLECTION}")

        ground_truth = generate_ground_truth_from_mongodb(
            n_samples=samples,
            min_title_length=min_title_length,
        )

        typer.echo(f"📊 Found {len(ground_truth)} questions matching criteria")

        if len(ground_truth) < samples:
            typer.echo(
                f"⚠️  Warning: Only found {len(ground_truth)} questions, requested {samples}"
            )

        if not ground_truth:
            typer.echo("❌ Error: No ground truth data generated", err=True)
            raise typer.Exit(1)

        save_ground_truth(ground_truth, output)
        output_path = Path(output)
        if output_path.suffix != ".json":
            output_path = output_path.with_suffix(".json")

        typer.echo(f"💾 Saved ground truth to {output_path} (JSON format)")
        typer.echo(
            f"\n✅ Successfully generated {len(ground_truth)} ground truth examples"
        )
        typer.echo(f"   Output: {output_path}")
        typer.echo("\n💡 Tip: Review and edit the file to remove low-quality examples")
    except Exception as e:
        _handle_error(e)


@app.command()
def evaluate(
    ground_truth: str = typer.Option(
        DEFAULT_GROUND_TRUTH_OUTPUT,
        "--ground-truth",
        "-g",
        help="Path to ground truth JSON file",
    ),
    output: str = typer.Option(
        DEFAULT_OUTPUT_PATH,
        "--output",
        "-o",
        help="Path to output JSON file for results",
    ),
    judge_model: str = typer.Option(
        None,
        "--judge-model",
        "-j",
        help=f"Model to use for judging (default: {DEFAULT_JUDGE_MODEL})",
    ),
    max_samples: int = typer.Option(
        15,
        "--max-samples",
        "-n",
        help="Maximum number of questions to evaluate (default: 15). Use 0 to evaluate all.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Evaluate MongoDB agent using ground truth and judge LLM"""
    try:
        ground_truth_path = Path(ground_truth)
        if not ground_truth_path.exists():
            typer.echo(
                f"❌ Error: Ground truth file not found: {ground_truth_path}", err=True
            )
            raise typer.Exit(1)

        with open(ground_truth_path, "r") as f:
            total_questions = len(json.load(f))

        # Determine how many questions to evaluate
        num_to_evaluate = max_samples if max_samples > 0 else total_questions

        typer.echo(f"📊 Loaded {total_questions} questions from ground truth")
        if max_samples > 0 and max_samples < total_questions:
            typer.echo(
                f"🎲 Will evaluate {num_to_evaluate} random questions (sampling from {total_questions})"
            )
        else:
            typer.echo(f"📝 Will evaluate all {num_to_evaluate} questions")
        typer.echo(f"📁 Ground truth: {ground_truth_path}")
        typer.echo(f"💾 Output: {output}")

        agent = _init_mongodb_agent(verbose)
        model_to_use = judge_model or DEFAULT_JUDGE_MODEL
        if verbose:
            typer.echo(f"⚖️  Using judge model: {model_to_use}")

        typer.echo(f"\n🚀 Starting evaluation of {num_to_evaluate} questions...")
        typer.echo(
            "⏳ This may take a while (each question requires agent + judge evaluation)...\n"
        )

        async def execute_evaluation():
            result_path = await evaluate_agent(
                ground_truth_path=ground_truth_path,
                agent_query_fn=lambda q: agent.query(q),
                output_path=output,
                judge_model=model_to_use,
                max_samples=max_samples if max_samples > 0 else None,
            )

            with open(result_path, "r") as f:
                results_data = json.load(f)

            summary = results_data.get("summary", {})
            typer.echo("\n" + "=" * 60)
            typer.echo("📊 EVALUATION SUMMARY")
            typer.echo("=" * 60)
            typer.echo(
                f"✅ Questions evaluated: {results_data.get('num_questions', 0)}"
            )
            typer.echo(f"📈 Average Hit Rate: {summary.get('avg_hit_rate', 0.0):.2f}")
            typer.echo(f"📈 Average MRR: {summary.get('avg_mrr', 0.0):.2f}")
            typer.echo(
                f"⚖️  Average Judge Score: {summary.get('avg_judge_score', 0.0):.2f}"
            )
            typer.echo(
                f"🎯 Average Combined Score: {summary.get('avg_combined_score', 0.0):.2f}"
            )
            typer.echo(f"🔢 Total Tokens: {summary.get('total_tokens', 0):,}")
            typer.echo(f"💾 Results saved to: {result_path}")
            typer.echo("=" * 60)

            if verbose:
                typer.echo("\n📋 Detailed results:")
                for i, result in enumerate(results_data.get("results", [])[:5], 1):
                    typer.echo(f"\n  {i}. {result.get('question', 'N/A')[:50]}...")
                    typer.echo(f"     Hit Rate: {result.get('hit_rate', 0.0):.2f}")
                    typer.echo(f"     MRR: {result.get('mrr', 0.0):.2f}")
                    typer.echo(
                        f"     Judge Score: {result.get('judge_score', 0.0):.2f}"
                    )
                    typer.echo(
                        f"     Combined Score: {result.get('combined_score', 0.0):.2f}"
                    )

            return result_path

        _run_async(execute_evaluation, verbose)
    except Exception as e:
        _handle_error(e, verbose)


if __name__ == "__main__":
    app()
