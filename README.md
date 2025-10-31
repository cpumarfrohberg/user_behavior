# User Behavior: Discover User Interaction Patterns

A system for analyzing user behavior patterns from StackExchange discussions, building knowledge graphs in Neo4j, and providing insights through an agent-based architecture.

## Architecture

- **Data Pipeline**: StackExchange → MongoDB → Neo4j knowledge graph
- **Agents**: Orchestrator, RAG Agent, Cypher Query Agent
- **Interface**: CLI, Streamlit, FastAPI

## Prerequisites

```bash
# Install dependencies
uv sync

# Install and start Ollama
brew install ollama  # macOS
ollama serve
ollama pull phi3:mini
```

## Quick Start

```bash
# Start services
docker-compose up -d  # MongoDB + Neo4j
ollama serve           # LLM server

# Run CLI
uv run ask "What are common user behavior patterns?" --verbose
uv run ask "How do users react to confusing interfaces?" --search-type sentence_transformers
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

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=phi3:mini

# Optional
STACKEXCHANGE_API_KEY=your_key
LOG_LEVEL=INFO
```

## CLI Usage

```bash
uv run ask <question> [--search-type minsearch|sentence_transformers] [--verbose]
```

## License

MIT License
