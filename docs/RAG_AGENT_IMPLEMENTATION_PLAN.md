# RAG Agent Implementation Plan

**Goal**: Implement RAG Agent with repetitive tool calls (like reference notebook) - working today with tests

**Timeline**: Today (~4-6 hours)

---

## Overview

Replicate the `summary_agent.ipynb` pattern where agent makes multiple tool calls (searches) in a single run. This allows evaluation of agent-guided multi-search vs single-search baseline.

---

## Architecture

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ pydantic-ai     │  ← Agent orchestrates multiple tool calls
│ Agent           │
└────────┬────────┘
         │
         ├───► search_documents(query) ──► SearchIndex
         │                                 (pre-loaded from MongoDB)
         ├───► search_documents(query)
         │
         └───► search_documents(query)

         ▼
┌─────────────────┐
│ Structured      │
│ Output Model    │  ← RAGAnswer with answer, sources, reasoning
└─────────────────┘
```

---

## Step-by-Step Implementation

### Step 1: Create Agent Module Structure (15 min)

**File**: `rag_agent/__init__.py`
- Create new package for agent code

**File**: `rag_agent/tools.py`
- Tool function: `search_documents(query: str) -> List[SearchResult]`
- Wraps existing `SearchIndex.search()`
- Returns structured `SearchResult` objects

**File**: `rag_agent/agent.py`
- Main agent class: `RAGAgent`
- Initializes `pydantic_ai.Agent` with tools
- Handles document loading from MongoDB
- Event handler for tracking tool calls

**File**: `rag_agent/models.py`
- Pydantic models for agent output (reuse existing `RAGAnswer`)

**File**: `rag_agent/events.py`
- Event handler to track all tool calls
- Stores tool calls for evaluation

---

### Step 2: Implement Search Tool (30 min)

**Key Requirements**:
- Pre-load documents from MongoDB into SearchIndex
- Tool function must be thread-safe (index is read-only during queries)
- Return structured results compatible with agent

**Implementation**:
```python
# rag_agent/tools.py
from typing import List
from pydantic_ai import Tool
from source.models import SearchResult
from search.search_utils import SearchIndex

# Global search index (loaded once, used by tool)
_search_index: SearchIndex | None = None

def initialize_search_index(config: RAGConfig) -> None:
    """Pre-load documents into search index"""
    global _search_index
    _search_index = SearchIndex(config.search_type)
    # Load documents from MongoDB
    # ... use existing TextRAG.load_from_mongodb logic

@Tool
def search_documents(query: str, num_results: int = 5) -> List[SearchResult]:
    """
    Search the document index for relevant content.

    Use this tool to find information about user behavior patterns,
    questions, answers, and discussions from StackExchange.

    Args:
        query: Search query string (e.g., "user frustration", "satisfaction patterns")
        num_results: Number of results to return (default: 5)

    Returns:
        List of search results with content, source, similarity scores
    """
    if _search_index is None:
        raise RuntimeError("Search index not initialized. Call initialize_search_index first.")

    results = _search_index.search(query=query, num_results=num_results)

    # Convert to SearchResult models
    return [
        SearchResult(
            content=doc.get("content", ""),
            source=doc.get("source", "unknown"),
            title=doc.get("title"),
            similarity_score=doc.get("similarity_score"),
            tags=doc.get("tags", [])
        )
        for doc in results
    ]
```

---

### Step 3: Create Agent Class (45 min)

**File**: `rag_agent/agent.py`

**Requirements**:
- Initialize pydantic-ai Agent with Ollama backend
- System prompt guiding agent to make multiple searches
- Event handler to track tool calls
- Structured output using RAGAnswer model

**Key Challenges**:
1. **Ollama Support**: pydantic-ai may not directly support Ollama. Options:
   - Use OpenAI API (if available) - fastest path
   - Create Ollama adapter if needed
   - Check pydantic-ai docs for Ollama support

2. **Agent Instructions**: Guide agent to make 3-8 searches adaptively (adjust based on dataset size and query complexity)

**Implementation**:
```python
# rag_agent/agent.py
import logging
from typing import Any, List
from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent

from config import DEFAULT_RAG_MODEL, RAGConfig
from rag_agent.tools import search_documents, initialize_search_index
from source.models import RAGAnswer

logger = logging.getLogger(__name__)

# Store tool calls for evaluation
_tool_calls: List[dict] = []

async def track_tool_calls(ctx: Any, event: Any) -> None:
    """Event handler to track all tool calls for evaluation"""
    # Handle nested async streams
    if hasattr(event, "__aiter__"):
        async for sub in event:
            await track_tool_calls(ctx, sub)
        return

    # Track function tool calls
    if isinstance(event, FunctionToolCallEvent):
        tool_call = {
            "tool_name": event.part.tool_name,
            "args": event.part.args,
            "timestamp": ...  # Add timestamp
        }
        _tool_calls.append(tool_call)
        logger.info(f"🔧 Tool Call: {event.part.tool_name} with args: {event.part.args}")

class RAGAgent:
    """RAG Agent that makes repetitive tool calls for better retrieval"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.agent = None
        self.search_index = None

    def initialize(self) -> None:
        """Initialize search index and create agent"""
        # Initialize search index (pre-load documents)
        initialize_search_index(self.config)

        # System prompt guiding agent to make multiple searches
        instructions = """
You are a RAG agent specialized in analyzing user behavior patterns from StackExchange discussions.

Your workflow:
1. **Exploration Phase (1-2 searches)**: Start with broad queries to understand the topic
   - Examples: "user behavior patterns", "satisfaction analysis", "frustration indicators"

2. **Deep Retrieval Phase (2-6 searches)**: Make specific, focused searches on subtopics
   - Examples: "user frustration with loading times", "satisfaction with search features"
   - Use varied query formulations to retrieve diverse perspectives

3. **Synthesis Phase**: Combine information from all searches to provide comprehensive answer

Rules:
- Make 3-8 searches total (adjust based on query complexity and result quality)
- Use diverse query formulations for the same topic
- Focus searches on specific aspects: frustration patterns, satisfaction factors, usability issues, etc.
- All information must come from search results
- Provide structured answer with sources and reasoning

Output Format:
- Answer: Comprehensive response based on all searches
- Sources: List of sources from search results
- Confidence: Based on how well searches covered the topic
- Reasoning: Explain your search strategy and findings
""".strip()

        # Initialize model: Try Ollama first (default), fallback to OpenAI if needed
        # pydantic-ai supports Ollama via OllamaProvider with OpenAIChatModel
        try:
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.ollama import OllamaProvider
            from config import OLLAMA_HOST

            # Use Ollama with OpenAI-compatible interface
            model = OpenAIChatModel(
                model_name=self.config.ollama_model,
                provider=OllamaProvider(base_url=f"{OLLAMA_HOST}/v1"),
            )
            logger.info(f"Using Ollama model: {self.config.ollama_model} at {OLLAMA_HOST}")
        except (ImportError, Exception) as e:
            logger.warning(f"Ollama not available: {e}. Trying OpenAI...")
            # Fallback: Use OpenAI API if available
            try:
                from pydantic_ai.models.openai import OpenAIModel
                import os
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    model = OpenAIModel(model="gpt-4o-mini")
                    logger.info("Using OpenAI model: gpt-4o-mini")
                else:
                    raise ValueError("OPENAI_API_KEY not found")
            except (ImportError, ValueError) as e2:
                raise RuntimeError(
                    f"No supported model backend available. "
                    f"Ollama error: {e}. OpenAI error: {e2}"
                )

        # Create agent
        self.agent = Agent(
            name="rag_agent",
            model=model,
            tools=[search_documents],
            instructions=instructions,
            output_type=RAGAnswer,
        )

    async def query(self, question: str) -> tuple[RAGAnswer, List[dict]]:
        """
        Run agent query and return answer + tool calls

        Returns:
            (answer, tool_calls) - Answer object and list of tool calls for evaluation
        """
        global _tool_calls
        _tool_calls = []  # Reset for each query

        if self.agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        # Run agent with event tracking
        result = await self.agent.run(
            question,
            event_stream_handler=track_tool_calls,
        )

        return result.output, _tool_calls.copy()
```

---

### Step 4: Handle Ollama Backend (30 min)

**✅ Verified**: pydantic-ai DOES support Ollama via provider pattern

**Implementation**:
- Use `OllamaProvider` from `pydantic_ai.providers.ollama`
- Combine with `OpenAIChatModel` from `pydantic_ai.models.openai`
- Configure base URL (default: `http://localhost:11434/v1`)
- Supports both local Ollama and Ollama Cloud

**Example**:
```python
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

model = OpenAIChatModel(
    model_name="llama3.2:3b",
    provider=OllamaProvider(base_url="http://localhost:11434/v1"),
)
```

**Fallback Strategy**:
- **Option 1 (Preferred)**: Use Ollama with local server (default)
  - No API key required
  - Works offline
  - Uses model from config (`OLLAMA_RAG_MODEL`)

- **Option 2**: Use OpenAI API (if available)
  - Requires `OPENAI_API_KEY` environment variable
  - Use `gpt-4o-mini` or `gpt-3.5-turbo` for cost efficiency
  - Fallback if Ollama is not available

**For MVP**: Use Ollama as primary (already configured), OpenAI as fallback

---

### Step 5: Add CLI Command (20 min)

**File**: `cli.py` (add new command)

```python
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
    """Ask a question using the RAG agent (makes multiple searches)"""
    import asyncio
    from rag_agent.agent import RAGAgent
    from source.text_rag import RAGConfig, SearchType

    # Create config
    config = RAGConfig()
    config.collection = "stackexchange_content"
    if search_type.lower() == "sentence_transformers":
        config.search_type = SearchType.SENTENCE_TRANSFORMERS
    else:
        config.search_type = SearchType.MINSEARCH

    # Initialize and run agent
    agent = RAGAgent(config)
    agent.initialize()

    async def run():
        answer, tool_calls = await agent.query(question)

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

    asyncio.run(run())
```

---

### Step 6: Create Tests (90 min)

**File**: `tests/rag_agent/__init__.py`

**File**: `tests/rag_agent/test_tools.py`
- Test search_documents tool
- Test search index initialization
- Mock SearchIndex to avoid MongoDB dependency

**File**: `tests/rag_agent/test_agent.py`
- Test agent initialization
- Test agent query (mock tool calls)
- Test tool call tracking
- Test structured output

**File**: `tests/rag_agent/conftest.py`
- Fixtures for:
  - Mock search index
  - Sample documents
  - Agent config

**Key Test Cases**:
```python
# tests/rag_agent/test_agent.py
import pytest
from rag_agent.agent import RAGAgent
from rag_agent.tools import initialize_search_index
from source.text_rag import RAGConfig

@pytest.fixture
def mock_search_index(monkeypatch):
    """Mock SearchIndex to avoid MongoDB dependency"""
    # Create mock that returns sample results
    ...

def test_agent_initialization():
    """Test agent can be initialized"""
    config = RAGConfig()
    agent = RAGAgent(config)
    agent.initialize()
    assert agent.agent is not None

def test_agent_makes_multiple_searches():
    """Test agent makes multiple tool calls"""
    # Use TestModel from pydantic-ai for testing
    from pydantic_ai.testing import TestModel

    config = RAGConfig()
    agent = RAGAgent(config)
    agent.initialize()

    # Override with test model
    agent.agent = agent.agent.override(model=TestModel())

    answer, tool_calls = await agent.query("test question")

    # Verify multiple tool calls
    assert len(tool_calls) >= 3, "Agent should make at least 3 searches"
    assert len(tool_calls) <= 10, "Agent should not make excessive searches (>10)"
    assert all(call['tool_name'] == 'search_documents' for call in tool_calls)

def test_tool_call_tracking():
    """Test tool calls are properly tracked"""
    ...

def test_structured_output():
    """Test agent returns structured RAGAnswer"""
    ...
```

---

### Step 7: Integration & Verification (60 min)

**Tasks**:
1. Run agent with sample queries
2. Verify tool calls are tracked
3. Compare agent results vs single-search baseline
4. Fix any issues

**Test Queries**:
- "What are common user frustration patterns?"
- "How do users express satisfaction?"
- "What usability issues do users report?"

**Verification Checklist**:
- [ ] Agent initializes successfully
- [ ] Agent makes 3-8 tool calls per query (adaptive)
- [ ] Tool calls are tracked correctly
- [ ] Structured output is valid
- [ ] Search results are relevant
- [ ] All tests pass

---

## File Structure

```
user_behavior/
├── rag_agent/
│   ├── __init__.py
│   ├── agent.py           # Main agent class
│   ├── tools.py            # Search tool function
│   ├── models.py           # Output models (reuse existing)
│   └── events.py           # Event handlers
│
├── tests/
│   └── rag_agent/
│       ├── __init__.py
│       ├── conftest.py     # Test fixtures
│       ├── test_agent.py    # Agent tests
│       └── test_tools.py    # Tool tests
│
├── cli.py                  # Add agent_ask command
└── ...
```

---

## Dependencies Check

**Already Installed**:
- ✅ `pydantic-ai>=0.0.12` (supports Ollama via `OllamaProvider`)
- ✅ `pydantic>=2.0.0`
- ✅ `minsearch>=0.0.7`
- ✅ `ollama>=0.1.0` (for Ollama client)

**May Need**:
- ⚠️ `openai` (only if using OpenAI API as fallback, not required for Ollama)
  - Install: `pip install openai` or `uv add openai`
  - Note: Ollama is the default and doesn't require OpenAI package

---

## Quick Start Checklist

1. **Create package structure** (15 min)
   - [ ] Create `rag_agent/` directory
   - [ ] Add `__init__.py`, `agent.py`, `tools.py`

2. **Implement search tool** (30 min)
   - [ ] Create `search_documents` tool function
   - [ ] Add initialization function
   - [ ] Test tool manually

3. **Create agent class** (45 min)
   - [ ] Initialize pydantic-ai Agent
   - [ ] Add system prompt
   - [ ] Implement event handler
   - [ ] Test agent initialization

4. **Handle backend** (30 min)
   - [ ] Choose backend (OpenAI/Ollama)
   - [ ] Configure model
   - [ ] Test agent query

5. **Add CLI command** (20 min)
   - [ ] Add `agent_ask` to cli.py
   - [ ] Test command

6. **Write tests** (90 min)
   - [ ] Test tools
   - [ ] Test agent
   - [ ] Test integration
   - [ ] Run all tests

7. **Integration testing** (60 min)
   - [ ] Run sample queries
   - [ ] Verify tool calls
   - [ ] Compare with baseline
   - [ ] Fix issues

**Total Time**: ~4-5 hours

---

## Troubleshooting

### Issue: Ollama not working with pydantic-ai
**Solution**:
- Verify Ollama server is running: `ollama list`
- Check base URL matches config (`OLLAMA_HOST`, default: `http://localhost:11434`)
- Ensure model is available: `ollama pull llama3.2:3b`
- Use correct import pattern: `OllamaProvider` with `OpenAIChatModel` (see Step 4)

### Issue: Import error for OllamaProvider
**Solution**:
- Verify `pydantic-ai>=0.0.12` is installed and up-to-date
- Check pydantic-ai version supports Ollama provider (v0.0.12+ should work)

### Issue: Agent not making enough tool calls
**Solution**: Strengthen system prompt, adjust model temperature

### Issue: Tests failing
**Solution**: Use `TestModel` from pydantic-ai for deterministic testing

### Issue: Search index not initializing
**Solution**: Verify MongoDB connection, check document loading logic

---

## Next Steps (Post-MVP)

1. **Evaluation Script**: Compare agent vs baseline
2. **Tool Call Analysis**: Analyze search query patterns
3. **Optimization**: Tune prompt for better searches
4. **Ollama Integration**: Add proper Ollama support if needed
5. **Metrics**: Track tool call count, answer quality, latency

---

## Notes

- **Backend Choice**: ✅ Ollama is supported and is the default (faster to start, no API keys needed)
- **Ollama Integration**: Uses `OllamaProvider` with `OpenAIChatModel` (provider pattern)
- **Testing**: Use pydantic-ai's `TestModel` for fast, deterministic tests
- **Evaluation**: Tool calls are already tracked via event handler - ready for analysis
- **MVP Focus**: Get it working first, optimize later
- **Ollama Setup**: Ensure Ollama server is running and model is pulled (`ollama pull llama3.2:3b`)
