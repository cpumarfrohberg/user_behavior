# User Behavior: Discover User Interaction Patterns

A system for analyzing user behavior patterns from social media discussions, building knowledge graphs, and providing insights through an agent-based architecture.

## Architecture

### Data Pipeline
- **Collection**: Gathers user behavior discussions from StackExchange
- **Processing**: RAG → Data Extraction → Statement Building → Graph Building (Kuzu DB)

### Agent System
- **Orchestrator**: Manages conversation history and coordinates agents
- **RAG Agent**: Handles document retrieval and generation
- **Cypher Query Agent**: Executes graph database queries
- **Interface**: Streamlit + FastAPI + Kuzu Explorer

## Prerequisites

### Installing Dependencies

This project uses **uv** for dependency management. Install dependencies:

```bash
uv sync
```

### Installing Ollama
This project uses **Ollama** for LLM inference. Install it locally:

```bash
# macOS
brew install ollama

# Or download from https://ollama.ai/download
```

Start Ollama:
```bash
ollama serve
```

Pull the required model:
```bash
ollama pull phi3:mini
```

Other supported models:
- `tinyllama:1.1b`
- `phi3:mini` (default)
- `llama3.1:8b`
- `mistral:7b`

## Quick Start

### 1. Start Required Services

```bash
# Start MongoDB (using Docker)
docker-compose up -d

# Start Ollama (if not already running)
ollama serve
```

### 2. Run the CLI

```bash
# Basic query
uv run ask "What are common user behavior patterns?"

# With verbose output
uv run ask "How do users react to confusing interfaces?" --verbose

# Using sentence transformers search
uv run ask "What is user behavior?" --search-type sentence_transformers

# See all options
uv run ask --help
```

## CLI Usage

The CLI allows you to query the RAG system for user behavior insights:

```bash
# Basic usage
uv run ask <question>

# Options:
#   --search-type, -s    : 'minsearch' (default) or 'sentence_transformers'
#   --verbose, -v        : Show detailed output
```

### Example Commands

```bash
# Ask about user behavior patterns
uv run ask "What are common user behavior patterns?" -v

# Query with sentence transformers search
uv run ask "How do users react to confusing interfaces?" \
  --search-type sentence_transformers

# Get detailed feedback
uv run ask "What is cognitive load in UX?" --verbose
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# MongoDB connection
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=user_behavior

# Ollama configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=phi3:mini

# Optional: StackExchange API (for data collection)
STACKEXCHANGE_API_KEY=your_key

# Optional: Logging
LOG_LEVEL=INFO
```

### MongoDB Setup

The project requires a MongoDB instance with the `stackexchange_content` collection. The CLI loads documents from this collection to answer queries.

## Usage Examples

### RAG Queries
- "What are common user behavior patterns?"
- "How do users react to confusing interfaces?"

### Cypher Queries
- "Show me frustration behavior patterns"
- "Find relationships between interface complexity and user behavior"

## Next Steps

The current implementation includes the RAG system for querying StackExchange data. The following features are planned for future development:

### 1. Orchestrator Agent

An orchestrator agent will manage conversation flow and route queries to appropriate agents:

- **Conversation management**: Maintain context and history across user interactions
- **Query routing**: Determine whether a query requires RAG retrieval or graph database query
- **Response synthesis**: Combine outputs from multiple agents into coherent answers
- **Error handling**: Manage fallback strategies when agents fail

```python
# Planned orchestrator interface
orchestrator = OrchestratorAgent()
response = orchestrator.process_query(user_query, conversation_history)
```

### 2. Cypher Query Agent

A specialized agent for executing graph database queries on Kuzu DB:

- **Query generation**: Convert natural language questions into Cypher queries
- **Graph traversal**: Execute complex relationship queries across user behavior nodes
- **Result interpretation**: Transform graph results into natural language answers
- **Integration**: Connect Kuzu DB with the agent system

```python
# Planned Cypher agent interface
cypher_agent = CypherQueryAgent(kuzu_db_path)
response = cypher_agent.query("Show me frustration behavior patterns")
```

### 3. Graph Database Integration

Build a knowledge graph from StackExchange discussions:

- **Data extraction**: Parse discussions to extract entities and relationships
- **Graph building**: Create nodes and edges representing user behaviors and patterns
- **Cypher querying**: Enable complex graph traversals and pattern matching

### 4. Unified Interface

Combine all components into a single interface:

- **Agent orchestration**: Coordinate RAG and Cypher agents
- **Streamlit frontend**: Interactive web UI for querying
- **FastAPI backend**: RESTful API for programmatic access

## License

MIT License
