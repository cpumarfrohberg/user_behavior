# CLI for User Behavior Analysis using StackExchange RAG

import typer
from pymongo import MongoClient

from config import (
    DEFAULT_BEST_RESULTS_COUNT,
    DEFAULT_GRID_SEARCH_CHUNK_SIZES,
    DEFAULT_GRID_SEARCH_OVERLAPS,
    DEFAULT_GRID_SEARCH_RESULTS_OUTPUT,
    DEFAULT_GRID_SEARCH_SAMPLES,
    DEFAULT_GRID_SEARCH_TOP_KS,
    DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH,
    DEFAULT_GROUND_TRUTH_OUTPUT,
    DEFAULT_GROUND_TRUTH_SAMPLES,
    DEFAULT_SEARCH_TYPE,
    DEFAULT_TOP_K,
    MONGODB_COLLECTION,
    MONGODB_DB,
    MONGODB_URI,
    SearchType,
)
from evals.generate_ground_truth import (
    generate_ground_truth_from_mongodb,
    save_ground_truth,
)
from evals.save_results import save_grid_search_results
from rag_agent.config import RAGConfig
from search.search_utils import RAGError
from search.simple_chunking import (
    evaluate_chunking_grid,
    evaluate_chunking_params,
    find_best_chunking_params,
)

app = typer.Typer()


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    search_type: str = typer.Option(
        str(DEFAULT_SEARCH_TYPE),
        "--search-type",
        "-s",
        help="Search type: 'minsearch' (MinSearch) or 'sentence_transformers' (SentenceTransformer). Default: sentence_transformers",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """DEPRECATED: Use 'agent-ask' instead. This command is no longer supported."""
    typer.echo("❌ This command has been deprecated.")
    typer.echo("💡 Use 'agent-ask' instead: uv run ask agent-ask \"your question\"")
    raise typer.Exit(1)


@app.command()
def agent_ask(
    question: str = typer.Argument(..., help="Question to ask the agent"),
    search_type: str = typer.Option(
        str(DEFAULT_SEARCH_TYPE),
        "--search-type",
        "-s",
        help="Search type: 'minsearch' or 'sentence_transformers'",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show tool calls"),
):
    """Ask a question using the RAG agent directly (makes multiple searches)"""
    import asyncio

    from rag_agent.agent import RAGAgent

    try:
        if verbose:
            typer.echo("📥 Initializing RAG Agent...")

        # Create config
        config = RAGConfig()
        config.collection = "questions"  # Use the correct collection name

        # Set search type based on parameter
        if search_type.lower() == "sentence_transformers":
            config.search_type = SearchType.SENTENCE_TRANSFORMERS
        elif search_type.lower() == "minsearch":
            config.search_type = SearchType.MINSEARCH
        else:
            config.search_type = DEFAULT_SEARCH_TYPE

        if verbose:
            typer.echo(f"🔍 Using search type: {config.search_type}")

        # Initialize agent
        agent = RAGAgent(config)
        agent.initialize()

        if verbose:
            typer.echo("✅ Agent initialized successfully!")
            typer.echo("🤖 Running agent query...")
        else:
            typer.echo("🤖 Running agent query (this may take a minute)...")

        async def run_query():
            try:
                answer, tool_calls = await agent.query(question)
            except Exception as e:
                typer.echo(f"❌ Error during agent query: {str(e)}", err=True)
                if verbose:
                    import traceback

                    typer.echo(traceback.format_exc(), err=True)
                raise

            typer.echo(f"\n❓ Question: {question}")
            typer.echo(f"💡 Answer: {answer.answer}")
            typer.echo(f"🎯 Confidence: {answer.confidence:.2f}")
            typer.echo(f"🔍 Tool Calls: {len(tool_calls)}")

            if verbose:
                typer.echo("\n📋 Tool Call History:")
                for i, call in enumerate(tool_calls, 1):
                    typer.echo(f"  {i}. {call['tool_name']}: {call['args']}")

            if answer.sources_used:
                typer.echo("\n📚 Sources:")
                for i, source in enumerate(answer.sources_used[:10], 1):
                    typer.echo(f"  {i}. {source}")

            if verbose and answer.reasoning:
                typer.echo(f"\n💭 Reasoning: {answer.reasoning}")

        asyncio.run(run_query())

    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def orchestrator_ask(
    question: str = typer.Argument(..., help="Question to ask"),
    search_type: str = typer.Option(
        str(DEFAULT_SEARCH_TYPE),
        "--search-type",
        "-s",
        help="Search type: 'minsearch' or 'sentence_transformers' (for RAG agent)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Ask a question using the Orchestrator Agent (intelligently routes to RAG or Cypher Query Agent)"""
    import asyncio

    from orchestrator.agent import OrchestratorAgent
    from orchestrator.config import OrchestratorConfig
    from orchestrator.tools import initialize_rag_agent

    try:
        if verbose:
            typer.echo("📥 Initializing Orchestrator Agent...")

        # Initialize RAG Agent with config (needed for orchestrator tools)
        rag_config = RAGConfig()
        rag_config.collection = "questions"

        # Set search type based on parameter
        if search_type.lower() == "sentence_transformers":
            rag_config.search_type = SearchType.SENTENCE_TRANSFORMERS
        elif search_type.lower() == "minsearch":
            rag_config.search_type = SearchType.MINSEARCH
        else:
            rag_config.search_type = DEFAULT_SEARCH_TYPE

        if verbose:
            typer.echo(f"🔍 RAG Agent will use search type: {rag_config.search_type}")

        # Initialize RAG Agent for orchestrator to use
        initialize_rag_agent(rag_config)

        # Create orchestrator config
        orchestrator_config = OrchestratorConfig()

        if verbose:
            typer.echo("✅ RAG Agent initialized for orchestrator")

        # Initialize orchestrator
        orchestrator = OrchestratorAgent(orchestrator_config)
        orchestrator.initialize()

        if verbose:
            typer.echo("✅ Orchestrator initialized successfully!")
        else:
            typer.echo("🎯 Orchestrator is analyzing your question...")

        async def run_query():
            try:
                answer = await orchestrator.query(question)
            except Exception as e:
                typer.echo(f"❌ Error during orchestrator query: {str(e)}", err=True)
                if verbose:
                    import traceback

                    typer.echo(traceback.format_exc(), err=True)
                raise

            typer.echo(f"\n❓ Question: {question}")
            typer.echo(f"💡 Answer: {answer.answer}")
            typer.echo(f"🎯 Confidence: {answer.confidence:.2f}")
            typer.echo(f"🤖 Agents Used: {', '.join(answer.agents_used)}")

            if verbose:
                typer.echo(f"\n💭 Routing Reasoning: {answer.reasoning}")

            if answer.sources_used:
                typer.echo("\n📚 Sources:")
                for i, source in enumerate(answer.sources_used[:10], 1):
                    typer.echo(f"  {i}. {source}")

        asyncio.run(run_query())

    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


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
    """Generate ground truth dataset for chunking parameter evaluation"""
    try:
        from pathlib import Path

        from config import MONGODB_COLLECTION, MONGODB_DB

        typer.echo(f"📥 Connecting to MongoDB: {MONGODB_DB}.{MONGODB_COLLECTION}")

        # Generate ground truth using existing function
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

        # Save to file using existing function (ensures .json extension)
        save_ground_truth(ground_truth, output)

        # Get the actual output path (with .json extension ensured by save_ground_truth)
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
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


def _load_documents_from_mongodb() -> list[dict]:
    """Helper function to load and parse documents from MongoDB"""
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    collection_obj = db[MONGODB_COLLECTION]

    docs = list(collection_obj.find({}, {"_id": 0}))
    client.close()

    # Parse documents (same logic as TextRAG._parse_mongodb_documents)
    parsed_docs = []
    for doc in docs:
        content_parts = []
        if doc.get("title"):
            content_parts.append(doc["title"])
        if doc.get("body"):
            content_parts.append(doc["body"])

        parsed_docs.append(
            {
                "content": " ".join(content_parts),
                "title": doc.get("title", ""),
                "source": f"question_{doc.get('question_id', 'unknown')}",
                "tags": doc.get("tags", []),
            }
        )

    return parsed_docs


@app.command()
def evaluate_chunking(
    ground_truth_file: str = typer.Option(
        DEFAULT_GROUND_TRUTH_OUTPUT,
        "--ground-truth",
        "-g",
        help="Path to ground truth JSON file",
    ),
    chunk_sizes: str = typer.Option(
        None,
        "--chunk-sizes",
        "-c",
        help="Comma-separated chunk sizes for grid search (e.g., '300,500,1000')",
    ),
    overlaps: str = typer.Option(
        None,
        "--overlaps",
        help="Comma-separated overlaps for grid search (e.g., '0,15,50')",
    ),
    top_ks: str = typer.Option(
        None,
        "--top-ks",
        "-k",
        help="Comma-separated top_k values for grid search (e.g., '5,10,15')",
    ),
    n_samples: int = typer.Option(
        DEFAULT_GRID_SEARCH_SAMPLES,
        "--samples",
        "-n",
        help="Number of random combinations to test",
    ),
    search_type: str = typer.Option(
        DEFAULT_SEARCH_TYPE,
        "--search-type",
        "-s",
        help="Search type: 'minsearch' or 'sentence_transformers'",
    ),
    best_n: int = typer.Option(
        DEFAULT_BEST_RESULTS_COUNT,
        "--best-n",
        "-b",
        help="Number of best results to display",
    ),
    output: str = typer.Option(
        DEFAULT_GRID_SEARCH_RESULTS_OUTPUT,
        "--output",
        "-o",
        help="Path to save grid search results CSV file",
    ),
    save: bool = typer.Option(
        True,
        "--save/--no-save",
        help="Save results to CSV file",
    ),
):
    """Evaluate chunking parameters using randomized grid search

    Tests random combinations of chunk_size, overlap, and top_k parameters.
    Uses default ranges if not provided.
    """
    import json
    from pathlib import Path

    try:
        # Load ground truth
        ground_truth_path = Path(ground_truth_file)
        if not ground_truth_path.exists():
            typer.echo(
                f"❌ Error: Ground truth file not found: {ground_truth_path}", err=True
            )
            raise typer.Exit(1)

        typer.echo(f"📥 Loading ground truth from {ground_truth_path}...")
        with open(ground_truth_path, "r") as f:
            ground_truth = json.load(f)

        if not ground_truth:
            typer.echo("❌ Error: Ground truth file is empty", err=True)
            raise typer.Exit(1)

        typer.echo(f"✅ Loaded {len(ground_truth)} ground truth examples")

        # Load documents from MongoDB
        typer.echo(
            f"📥 Loading documents from MongoDB: {MONGODB_DB}.{MONGODB_COLLECTION}..."
        )
        documents = _load_documents_from_mongodb()
        typer.echo(f"✅ Loaded {len(documents)} documents")

        # Parse search type
        if search_type.lower() == "sentence_transformers":
            search_type_enum = SearchType.SENTENCE_TRANSFORMERS
        else:
            search_type_enum = SearchType.MINSEARCH

        # Parse grid search parameters
        if chunk_sizes:
            chunk_sizes_list = [int(x.strip()) for x in chunk_sizes.split(",")]
        else:
            chunk_sizes_list = DEFAULT_GRID_SEARCH_CHUNK_SIZES

        if overlaps:
            overlaps_list = [int(x.strip()) for x in overlaps.split(",")]
        else:
            overlaps_list = DEFAULT_GRID_SEARCH_OVERLAPS

        if top_ks:
            top_ks_list = [int(x.strip()) for x in top_ks.split(",")]
        else:
            top_ks_list = DEFAULT_GRID_SEARCH_TOP_KS

        typer.echo("\n🔍 Running grid search...")
        typer.echo(f"   chunk_sizes: {chunk_sizes_list}")
        typer.echo(f"   overlaps: {overlaps_list}")
        typer.echo(f"   top_ks: {top_ks_list}")
        typer.echo(f"   samples: {n_samples}")
        typer.echo(f"   search_type: {search_type_enum}")

        results = evaluate_chunking_grid(
            documents=documents,
            ground_truth=ground_truth,
            chunk_sizes=chunk_sizes_list,
            overlaps=overlaps_list,
            top_ks=top_ks_list,
            n_samples=n_samples,
            search_type=search_type_enum,
        )

        typer.echo(f"✅ Evaluated {len(results)} parameter combinations")

        # Find and display best results
        best = find_best_chunking_params(results, n=best_n)

        typer.echo(f"\n🏆 Top {len(best)} Results:")
        for i, result in enumerate(best, 1):
            typer.echo(f"\n{i}. Score: {result['score']:.3f}")
            typer.echo(
                f"   chunk_size={result['chunk_size']}, overlap={result['overlap']}, top_k={result['top_k']}"
            )
            typer.echo(
                f"   Hit Rate: {result['hit_rate']:.3f}, MRR: {result['mrr']:.3f}, Tokens: {result['num_tokens']:.1f}"
            )

        # Save results if requested
        if save:
            metadata = {
                "search_type": str(search_type_enum),
                "chunk_sizes": chunk_sizes_list,
                "overlaps": overlaps_list,
                "top_ks": top_ks_list,
                "n_samples": n_samples,
                "ground_truth_file": str(ground_truth_path),
                "num_ground_truth_samples": len(ground_truth),
                "num_documents": len(documents),
            }

            saved_path = save_grid_search_results(
                results=results,
                output_path=output,
                metadata=metadata,
            )

            typer.echo(f"\n💾 Saved results to {saved_path}")

        typer.echo("\n✅ Grid search complete!")

    except FileNotFoundError as e:
        typer.echo(f"❌ Error: File not found: {str(e)}", err=True)
        raise typer.Exit(1)
    except json.JSONDecodeError as e:
        typer.echo(f"❌ Error: Invalid JSON in ground truth file: {str(e)}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
