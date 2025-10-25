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

## Quick Start

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Collect data
uv run python stream_stackexchange/setup_data_pipeline.py

# Start application
uv run uvicorn main:app --reload --port 8000 &
uv run streamlit run app.py --server.port 8501
```

## Configuration

```bash
# Required environment variables
OPENAI_API_KEY=your_key
STACKEXCHANGE_API_KEY=your_key
MONGODB_URI=mongodb://localhost:27017/
KUZU_DB_PATH=./data/kuzu_db
DEFAULT_TAG=user-behavior
```

## Usage Examples

### RAG Queries
- "What are common user behavior patterns?"
- "How do users react to confusing interfaces?"

### Cypher Queries
- "Show me frustration behavior patterns"
- "Find relationships between interface complexity and user behavior"

## Deployment

```bash
# Docker
docker-compose up --build

# Services: FastAPI, Streamlit, MongoDB, Kuzu DB
```

## License

MIT License
