# User Behavior: Discover User Interaction Patterns

A system for analyzing user behavior patterns from StackExchange discussions, building knowledge graphs in Neo4j, and providing insights through an agent-based architecture with optimized RAG retrieval.

## Architecture

- **Data Pipeline**: StackExchange → MongoDB → Neo4j knowledge graph
- **Agents**: Orchestrator, RAG Agent, Cypher Query Agent
- **Interface**: CLI, Streamlit, FastAPI
- **Search**: Vector search (SentenceTransformers) for semantic retrieval
- **Evaluation**: Automated chunking parameter optimization

## Prerequisites

```bash
# Install dependencies
uv sync
```

## Quick Start

```bash
# Start all services (MongoDB + Neo4j + Ollama)
docker-compose up -d

# Ask questions (uses vector search by default)
uv run ask "What are common user behavior patterns?" --verbose
uv run ask "How do users react to confusing interfaces?"

# Switch to text search if needed
uv run ask "What causes user frustration?" --search-type minsearch
```

## Configuration

Create a `.env` file:

```bash
# MongoDB
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=stackexchange
MONGO_COLLECTION_NAME=questions

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password

# Ollama (managed by Docker)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b

# Optional
STACKEXCHANGE_API_KEY=your_key
LOG_LEVEL=INFO
```

## CLI Usage

### Ask Questions

Query the RAG system with natural language questions:

```bash
# Basic usage (default: vector search)
uv run ask "How do users behave when confused?"

# Verbose output
uv run ask "What causes user abandonment?" --verbose

# Use text search instead
uv run ask "Find discussions about frustration" --search-type minsearch
```

### Chunking Evaluation

Optimize chunking parameters for better retrieval performance:

#### 1. Generate Ground Truth

Create a ground truth dataset from MongoDB:

```bash
# Generate 50 samples (default)
uv run ask generate-ground-truth

# Custom number of samples
uv run ask generate-ground-truth --samples 100 --output evals/my_ground_truth.json

# With minimum title length filter
uv run ask generate-ground-truth --samples 50 --min-title-length 15
```

#### 2. Evaluate Chunking Parameters

Run randomized grid search to find optimal chunking parameters:

```bash
# Use default ranges (recommended)
uv run ask evaluate-chunking

# Custom parameter ranges
uv run ask evaluate-chunking \
  --chunk-sizes "200,300,500,1000" \
  --overlaps "0,15,50" \
  --top-ks "5,10" \
  --samples 20

# With custom ground truth file
uv run ask evaluate-chunking --ground-truth evals/my_ground_truth.json

# Use text search for evaluation (faster)
uv run ask evaluate-chunking --search-type minsearch

# Show top 10 results
uv run ask evaluate-chunking --best-n 10
```

#### Evaluation Workflow Example

```bash
# Step 1: Generate ground truth dataset
uv run ask generate-ground-truth --samples 50

# Step 2: Run evaluation (tests random combinations)
uv run ask evaluate-chunking --samples 10

# Step 3: Review top results
# Output shows: chunk_size, overlap, top_k, hit_rate, MRR, score
# Use best parameters in your RAG configuration
```

## Search Types

The system supports two search methods:

- **Vector Search (SentenceTransformers)** - Default
  - Semantic similarity search
  - Better for natural language queries
  - Handles synonyms and paraphrasing
  - Slower but more accurate

- **Text Search (MinSearch)**
  - Keyword-based search
  - Faster for exact matches
  - Good for technical terms and IDs
  - Use for performance-critical scenarios

Default: `SentenceTransformers` (vector search) for best semantic retrieval.

## License

MIT License
