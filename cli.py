# CLI for User Behavior Analysis using StackExchange RAG

import typer

from config import SearchType
from search.search_utils import RAGError
from source.text_rag import RAGConfig, TextRAG

app = typer.Typer()


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    search_type: str = typer.Option(
        "minsearch",
        "--search-type",
        "-s",
        help="Search type: 'minsearch' (MinSearch) or 'sentence_transformers' (SentenceTransformer)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Ask a question about user behavior patterns using RAG system"""
    try:
        if verbose:
            typer.echo("📥 Initializing RAG system...")

        # Create RAG with correct collection name and search type
        config = RAGConfig()
        config.collection = "stackexchange_content"  # Use the correct collection name

        # Set search type based on parameter
        if search_type.lower() == "sentence_transformers":
            config.search_type = SearchType.SENTENCE_TRANSFORMERS.value
        else:
            config.search_type = SearchType.MINSEARCH.value

        if verbose:
            typer.echo(f"🔍 Using search type: {config.search_type}")

        rag = TextRAG(config)

        # Load documents
        if verbose:
            typer.echo("📥 Loading documents from MongoDB...")
        rag.load_from_mongodb()

        if verbose:
            typer.echo("✅ Documents loaded successfully!")
            typer.echo("🔍 Processing query...")

        # Get answer
        response = rag.query(question)

        # Show result
        typer.echo(f"\n❓ Question: {question}")
        typer.echo(f"💡 Answer: {response.answer}")
        typer.echo(f"🎯 Confidence: {response.confidence:.2f}")

        if verbose and response.sources_used:
            typer.echo("\n📚 Sources used:")
            for i, source in enumerate(response.sources_used, 1):
                typer.echo(f"  {i}. {source}")

    except RAGError as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"❌ Unexpected Error: {str(e)}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
