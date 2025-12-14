# User Behavior: Discover User Interaction Patterns

A comprehensive system for analyzing user behavior patterns from StackExchange discussions, building knowledge graphs in Neo4j, and providing insights through an intelligent multi-agent architecture with optimized RAG retrieval and graph querying.

## Overview

This system combines **document-based search** (MongoDB) and **graph-based analysis** (Neo4j) to answer questions about user behavior patterns. An intelligent orchestrator routes questions to the appropriate agent(s) and synthesizes results into actionable insights.

## Architecture

### Data Pipeline
- **Data Collection**: StackExchange API → MongoDB (document storage)
- **Graph Construction**: MongoDB → Neo4j (knowledge graph with relationships)
- **ETL Process**: Automated extraction, transformation, and loading

### Multi-Agent System
- **Orchestrator Agent**: Routes questions to appropriate sub-agents and synthesizes results
- **MongoDB/RAG Agent**: Text search over StackExchange documents using MongoDB text search
- **Cypher Query Agent**: Graph traversal and pattern detection in Neo4j knowledge graph

### Features
- **Intelligent Routing**: Orchestrator automatically selects the best agent(s) for each question
- **Parallel Execution**: Can run both agents concurrently for comprehensive answers
- **Streaming Support**: Real-time answer streaming in Streamlit UI
- **Tool Call Limits**: Hard limits prevent excessive API calls (5 calls per query)
- **Cost Tracking**: Monitor token usage and costs via PostgreSQL
- **Evaluation Framework**: Automated evaluation with judge models

### Interfaces
- **Streamlit UI**: Interactive web interface with streaming responses (primary interface)
- **CLI**: Command-line interface for testing and evaluation (may be removed in published version)
- **Monitoring Dashboard**: Cost tracking and agent performance metrics

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- OpenAI API key (for LLM agents)
- MongoDB, PostgreSQL (via Docker Compose)
- Neo4j (external instance or local - configured via NEO4J_URI environment variable)

## Quick Start

### 1. Install Dependencies

```bash
# Install all dependencies using uv
uv sync
```

### 2. Start Services

```bash
# Start all services (MongoDB, Neo4j, PostgreSQL)
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
# MongoDB
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=stackexchange
MONGO_COLLECTION_NAME=questions

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password

# PostgreSQL (for monitoring)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/user_behavior_monitoring

# OpenAI (required for agents)
OPENAI_API_KEY=your_openai_api_key
OPENAI_RAG_MODEL=gpt-4o-mini  # or gpt-4o, gpt-3.5-turbo
OPENAI_JUDGE_MODEL=gpt-4o-mini

# Optional
STACKEXCHANGE_API_KEY=your_key  # For data collection
LOG_LEVEL=INFO
```

### 4. Run the Application

**Streamlit UI:**
```bash
streamlit run streamlit_app.py
```

Then open `http://localhost:8501` in your browser.

## Agent System

### Orchestrator Agent

The orchestrator intelligently routes questions to the appropriate agent(s):

- **RAG Agent Only**: For document retrieval, examples, case studies, text searches
- **Cypher Agent Only**: For graph traversal, relationships, correlations, pattern detection
- **Both Agents**: When both document evidence and graph analysis are needed (runs in parallel)

**Example Questions:**
- RAG: "What do users say about confusing interfaces?"
- Cypher: "What patterns lead to user frustration?"
- Both: "What are common frustrations and what patterns lead to them?"

### MongoDB/RAG Agent

Performs text search over StackExchange documents:

- **Text Search**: MongoDB text search for keyword-based retrieval
- **Tag Filtering**: Optional tag-based filtering for focused results
- **Tool Call Limit**: Maximum 5 searches per query (prevents excessive API calls)

**Features:**
- Early stopping when sufficient results found
- Relevance scoring and normalization
- Source tracking (question IDs)

### Cypher Query Agent

Executes graph queries on Neo4j knowledge graph:

- **Schema-Aware**: Dynamic schema injection for accurate query generation
- **Read-Only**: Validates queries to prevent write operations
- **Query Validation**: Syntax and safety checks before execution
- **Tool Call Limit**: Maximum 5 queries per question (prevents excessive API calls)
- **Performance Optimizations**: Schema truncation, query result limiting, and tool result size limiting

**Features:**
- Automatic schema retrieval and injection (truncated to prevent context overflow)
- Query validation (forbidden keywords, syntax checks)
- Error handling for syntax errors and connection issues
- Query result limiting (max 100 records) and tool result size limiting (max 50KB)

## CLI Usage (Testing Only)

> **Note**: The CLI is primarily for testing and evaluation purposes. It may be removed in the published version. Use the Streamlit UI for production queries.

### Ask Questions

```bash
# Basic usage
uv run python cli.py ask "How do users behave when confused?"

# Verbose output (shows tool calls, token usage)
uv run python cli.py ask "What causes user abandonment?" --verbose
```

### Evaluation

Evaluate agent performance using ground truth datasets:

```bash
# Generate ground truth dataset (MongoDB agent)
uv run python cli.py evaluate --generate-ground-truth --samples 50

# Run evaluation (MongoDB agent)
uv run python cli.py evaluate --ground-truth evals/ground_truth.json --max-questions 15

# Evaluate Cypher agent
uv run python cli.py evaluate-cypher-agent --max-samples 6 --verbose

# With custom judge model
uv run python cli.py evaluate --judge-model gpt-4o
```

### Chunking Parameter Optimization

Optimize RAG retrieval parameters:

```bash
# Generate ground truth
uv run python cli.py ask generate-ground-truth --samples 50

# Evaluate chunking parameters
uv run python cli.py ask evaluate-chunking --samples 20

# Custom parameter ranges
uv run python cli.py ask evaluate-chunking \
  --chunk-sizes "200,300,500,1000" \
  --overlaps "0,15,50" \
  --top-ks "5,10"
```

## Streamlit UI

The Streamlit interface provides an interactive way to query the system:

**Features:**
- Real-time streaming responses
- Tool call visualization
- Confidence scores and reasoning display
- Source tracking
- Cost and performance monitoring
- Agent selection visualization

**Usage:**
```bash
streamlit run streamlit_app.py
```

Then open `http://localhost:8501` in your browser.

## Monitoring & Cost Tracking

The system tracks agent performance and costs:

- **PostgreSQL Database**: Stores all agent runs, token usage, and costs
- **Cost Calculation**: Uses `genai-prices` library for accurate pricing
- **Performance Metrics**: Query time, token counts, tool call counts
- **Dashboard**: View recent logs and cost statistics in Streamlit UI

**Access Monitoring:**
- Streamlit UI: Navigate to "Monitoring" page
- Database: Connect to PostgreSQL at `localhost:5432`

## Testing

Run the test suite:

```bash
# Run all tests
uv run pytest

# Run specific test suite
uv run pytest tests/orchestrator/
uv run pytest tests/cypher_agent/
uv run pytest tests/mongodb_agent/

# With coverage
uv run pytest --cov=. --cov-report=html
```

## Project Structure

```
user_behavior/
├── orchestrator/          # Orchestrator agent (routing & synthesis)
├── mongodb_agent/         # RAG agent (document search)
├── cypher_agent/          # Cypher query agent (graph traversal)
├── config/                # Configuration and instructions
├── monitoring/            # Cost tracking and logging
├── evals/                 # Evaluation framework
├── stream_stackexchange/  # StackExchange data collection
├── neo4j_etl/             # ETL pipeline for Neo4j
├── tests/                 # Test suite
├── streamlit_app.py       # Streamlit UI (primary interface)
└── cli.py                 # CLI interface (testing only, may be removed)
```

## Implementation Status

### ✅ Completed
- Multi-agent architecture (Orchestrator, MongoDB, Cypher)
- Tool call limits with hard stops (both agents)
- Streaming support in Streamlit
- Cost tracking and monitoring
- Evaluation framework (MongoDB and Cypher agents)
- Parallel agent execution
- Instruction optimizations
- Orchestrator tools refactoring (DRY pattern)
- Cypher agent optimizations (schema truncation, result limiting)

### 📋 Planned
- Guardrails implementation
- Local LLM support
- Structured routing log enhancement

See `IMPLEMENTATION_PLAN.md` for detailed status and roadmap.

## Development

### Pre-commit Hooks

The project uses pre-commit hooks for code quality:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Code Quality

- **Linting**: Ruff
- **Formatting**: Ruff formatter
- **Type Checking**: Basedpyright (optional)

## License

MIT License
