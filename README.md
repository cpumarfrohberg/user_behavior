# Research Assistant

A RAG (Retrieval-Augmented Generation) powered research assistant for document analysis and question answering.

## Features

- **Document Processing**: Chunk and process various document formats
- **GitHub Integration**: Parse and analyze GitHub repositories
- **RAG Pipeline**: Advanced retrieval and generation capabilities
- **CLI Interface**: Easy-to-use command-line interface
- **Web API**: FastAPI-based REST API for programmatic access

## Prerequisites

- Python 3.11+
- Git
- uv (recommended) or pip

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd doc_assistant

# Install dependencies
uv sync

# Set up pre-commit hooks
uv run python -m pre_commit install
```

## Configuration

Create a `.env` file in the project root with your OpenAI API key:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

## CLI Usage

The CLI provides a simple interface to query GitHub repositories using RAG.

### Basic Usage

```bash
# Ask a question about the default repository (using default chunking)
uv run ra "What is this repository about?" 2000 1000

# Ask with custom chunking parameters
uv run ra "What is this repository about?" 1500 750

# Get help
uv run ra --help
```

### Examples

#### Basic Usage
```bash
# Simple question with default settings
uv run ra "What is this repository about?" 2000 0.5

# Get help
uv run ra --help
```

#### Text Search Examples
```bash
# Default text search - fast and lightweight
uv run ra "What contents are listed in this repo?" 2000 0.5

# Text search with custom chunking
uv run ra "How do I install this project?" 1500 0.75

# Text search with verbose output
uv run ra "What are the main features?" 3000 0.25 --verbose

# Text search on specific repository
uv run ra "How to contribute?" 2500 0.125 --owner facebook --repo react --verbose
```

#### Vector Search Examples
```bash
# Vector search with default model (all-MiniLM-L6-v2)
uv run ra "What is machine learning?" 2000 0.5 --search-type vector_sentence_transformers

# Vector search with specific model
uv run ra "How do I install this project?" 1500 0.75 --search-type vector_sentence_transformers --model all-MiniLM-L6-v2

# Vector search with higher quality model
uv run ra "What are the main features?" 3000 0.25 --search-type vector_sentence_transformers --model all-mpnet-base-v2

# Multilingual vector search
uv run ra "¿Qué es machine learning?" 2000 0.5 --search-type vector_sentence_transformers --model paraphrase-multilingual-MiniLM-L12-v2

# Vector search with custom repository
uv run ra "How to contribute?" 2500 0.125 --owner facebook --repo react --search-type vector_sentence_transformers --verbose
```

#### Chunking Strategy Examples
```bash
# Large chunks with high overlap (better context, fewer chunks)
uv run ra "Explain the architecture" 4000 0.8

# Small chunks with low overlap (more precise, more chunks)
uv run ra "Find specific functions" 1000 0.2

# Medium chunks with balanced overlap
uv run ra "What are the main features?" 2000 0.5

# No overlap (fastest processing)
uv run ra "Quick overview" 2000 0.0
```

#### File Type Filtering Examples
```bash
# Only Python files
uv run ra "How does the code work?" 2000 0.5 --extensions "py"

# Python and Markdown files
uv run ra "What is this project?" 2000 0.5 --extensions "py,md"

# Multiple file types
uv run ra "Documentation and code" 2000 0.5 --extensions "py,md,txt,json"

# Only documentation
uv run ra "How to use this?" 2000 0.5 --extensions "md,mdx"
```

#### Repository Examples
```bash
# Default repository (evidentlyai/docs)
uv run ra "What is this about?" 2000 0.5

# Microsoft VS Code repository
uv run ra "How to install VS Code?" 2000 0.5 --owner microsoft --repo vscode

# Facebook React repository
uv run ra "How to contribute to React?" 2000 0.5 --owner facebook --repo react

# Python FastAPI repository
uv run ra "How to use FastAPI?" 2000 0.5 --owner tiangolo --repo fastapi

# TensorFlow documentation
uv run ra "What is TensorFlow?" 2000 0.5 --owner tensorflow --repo tensorflow --extensions "md,rst"
```

#### Search Type Comparison Examples
```bash
# Compare text vs vector search on the same question
uv run ra "What is machine learning?" 2000 0.5  # Text search
uv run ra "What is machine learning?" 2000 0.5 --search-type vector_sentence_transformers  # Vector search

# Compare different vector models
uv run ra "How to use this library?" 2000 0.5 --search-type vector_sentence_transformers --model all-MiniLM-L6-v2
uv run ra "How to use this library?" 2000 0.5 --search-type vector_sentence_transformers --model all-mpnet-base-v2

# Compare chunking strategies
uv run ra "Explain the concept" 1000 0.2  # Small chunks
uv run ra "Explain the concept" 4000 0.8  # Large chunks
```

#### Advanced Examples
```bash
# Complex query with all options
uv run ra "How to implement authentication?" 3000 0.6 \
  --owner microsoft \
  --repo vscode \
  --extensions "ts,js,md" \
  --search-type vector_sentence_transformers \
  --model all-mpnet-base-v2 \
  --verbose

# Multilingual documentation search
uv run ra "¿Cómo instalar este proyecto?" 2000 0.5 \
  --search-type vector_sentence_transformers \
  --model paraphrase-multilingual-MiniLM-L12-v2 \
  --extensions "md,mdx"

# Technical deep dive with large chunks
uv run ra "Explain the machine learning algorithms used" 5000 0.9 \
  --search-type vector_sentence_transformers \
  --model all-mpnet-base-v2 \
  --verbose

# Quick FAQ lookup with small chunks
uv run ra "What are common issues?" 1000 0.1 \
  --extensions "md" \
  --verbose
```

#### Performance Testing Examples
```bash
# Test different chunk sizes
uv run ra "What is this?" 1000 0.5  # Small chunks
uv run ra "What is this?" 2000 0.5  # Medium chunks
uv run ra "What is this?" 4000 0.5  # Large chunks

# Test different overlap ratios
uv run ra "What is this?" 2000 0.0  # No overlap
uv run ra "What is this?" 2000 0.5  # 50% overlap
uv run ra "What is this?" 2000 0.9  # 90% overlap

# Test different models
uv run ra "What is this?" 2000 0.5 --search-type vector_sentence_transformers --model all-MiniLM-L6-v2      # Fast
uv run ra "What is this?" 2000 0.5 --search-type vector_sentence_transformers --model all-mpnet-base-v2     # Quality
uv run ra "What is this?" 2000 0.5 --search-type vector_sentence_transformers --model paraphrase-multilingual-MiniLM-L12-v2  # Multilingual
```

### Search Types

#### Text Search (Default)
- **Method**: Minsearch text-based search
- **Pros**: Fast, lightweight, no additional dependencies
- **Best for**: Exact matches, keyword searches

#### Vector Search
- **Method**: SentenceTransformers embeddings with cosine similarity
- **Pros**: Better semantic understanding, handles synonyms and context
- **Best for**: Conceptual questions, semantic similarity
- **Models Available**:
  - `all-MiniLM-L6-v2` (22MB) - Fast, good general purpose
  - `all-mpnet-base-v2` (420MB) - Higher quality
  - `paraphrase-multilingual-MiniLM-L12-v2` (118MB) - Multilingual support

### Default Configuration
- **Repository**: `evidentlyai/docs`
- **File Extensions**: `md`, `mdx` (Markdown files)
- **Search Type**: `text`
- **Model**: `gpt-4o-mini`
- **Chunk Size**: 2000 characters
- **Chunk Overlap**: 0.5 (50% overlap)
- **Search Results**: 5 documents

## License

MIT License
