# CLI for Research Assistant using GitHub repository RAG

import typer

from config import (
    ChunkingConfig,
    RepositoryConfig,
    SearchType,
    SentenceTransformerModel,
)
from core.text_rag import TextRAG
from prompt.search_utils import RAGError

app = typer.Typer()

# Global RAG instance
rag = None


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    chunk_size: int = typer.Argument(
        ChunkingConfig.DEFAULT_SIZE.value, help="Size of document chunks in characters"
    ),
    overlap: float = typer.Argument(
        ChunkingConfig.DEFAULT_OVERLAP.value,
        help="Overlap ratio between chunks (0.0-1.0)",
    ),
    search_type: str = typer.Option(
        SearchType.TEXT.value,
        "--search-type",
        "-s",
        help="Search type: text, vector_minsearch, vector_sentence_transformers",
    ),
    model_name: str = typer.Option(
        SentenceTransformerModel.ALL_MINILM_L6_V2.value,
        "--model",
        "-m",
        help="SentenceTransformer model name (only for vector_sentence_transformers)",
    ),
    repo_owner: str = typer.Option(
        RepositoryConfig.DEFAULT_OWNER.value,
        "--owner",
        "-o",
        help="GitHub repository owner",
    ),
    repo_name: str = typer.Option(
        RepositoryConfig.DEFAULT_NAME.value,
        "--repo",
        "-r",
        help="GitHub repository name",
    ),
    extensions: str = typer.Option(
        ",".join(RepositoryConfig.DEFAULT_EXTENSIONS.value),
        "--extensions",
        "-e",
        help="Comma-separated file extensions to include (e.g., md,mdx)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """Ask a question and get an answer from GitHub repository using text-based RAG"""

    global rag

    try:
        # Parse extensions
        allowed_extensions = (
            set(extensions.split(","))
            if extensions
            else RepositoryConfig.DEFAULT_EXTENSIONS.value
        )

        if verbose:
            typer.echo(f"🔍 Searching for: {question}")
            typer.echo(f"📁 Repository: {repo_owner}/{repo_name}")
            typer.echo(f"📄 Extensions: {allowed_extensions}")

        # Initialize RAG if not already done
        if rag is None:
            if verbose:
                typer.echo("📥 Loading repository data...")

            # Calculate step from overlap ratio
            chunk_step = int(chunk_size * (1 - overlap))

            # Initialize and load repository using TextRAG
            rag = TextRAG(search_type=search_type, model_name=model_name)
            rag.load_repository(
                repo_owner=repo_owner,
                repo_name=repo_name,
                allowed_extensions=allowed_extensions,
                chunk_size=chunk_size,
                chunk_step=chunk_step,
            )

            if verbose:
                typer.echo(f"📚 Loaded {len(rag.documents)} files")

        # Get answer from RAG
        rag_response = rag.query(question)

        typer.echo(f"\n❓ Question: {question}")
        typer.echo(f"💡 Answer: {rag_response.answer}")
        typer.echo(f"🎯 Confidence: {rag_response.confidence:.2f}")

        # Display the correct search method
        if search_type == "vector_sentence_transformers":
            typer.echo("🔧 Method: vector search (SentenceTransformers)")
        elif search_type == "vector_minsearch":
            typer.echo("🔧 Method: vector search (Minsearch)")
        else:
            typer.echo("🔧 Method: text search")

        if verbose and rag_response.sources_used:
            typer.echo("\n📚 Sources used:")
            for i, source in enumerate(rag_response.sources_used, 1):
                typer.echo(f"  {i}. {source}")

            if rag_response.reasoning:
                typer.echo(f"\n💭 Reasoning: {rag_response.reasoning}")

    except RAGError as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        typer.echo("💡 Please check your input and try again.", err=True)
        raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"❌ Unexpected Error: {str(e)}", err=True)
        typer.echo("💡 Please check your configuration and try again.", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
