# Implementation Plan: MongoDB Text Search and Cypher Agents

## Current State
- ✅ Evaluation system complete (compatible with agent format)
- ✅ Orchestrator agent exists (routes to RAG and Cypher agents)
- ✅ MongoDB agent exists but pre-loads all documents (performance issue)
- ❌ Cypher agent not implemented (placeholder only)
- ✅ Neo4j schema defined (User, Question, Answer, Comment, Tag nodes with relationships)
- ✅ Ground truth format compatible (`expected_sources` matches `sources_used`)

## Architecture Decisions
- **Keep OpenAI models** for now (migrate to Ollama later - just swap model provider)
- **Keep LLM orchestrator** (intelligent routing - cost acceptable with local models later)
- **MongoDB agent**: Use MongoDB native text search with intelligent tag filtering (no semantic search)
- **Cypher agent**: Natural language → Cypher query generation
- **Keep agent behavior**: LLM decides query construction, tag filtering, multiple queries if needed

## Key Simplifications
- **Remove semantic search**: MongoDB text search + tags is sufficient for StackExchange data
- **No SentenceTransformers**: Eliminates model loading, embeddings, memory overhead
- **On-demand queries**: Direct MongoDB queries, no pre-loading
- **Agent decides**: LLM constructs MongoDB queries and selects tags intelligently

## Implementation Steps

### Step 1: Refactor MongoDB Agent - On-Demand Text Search

**File: `rag_agent/agent.py`**
- Remove `_load_from_mongodb()` pre-loading method
- Remove `_load_documents()` pre-loading method
- Remove `SearchIndex` initialization in `initialize()`
- Keep MongoDB connection only (no pre-loading, no index)
- Remove SentenceTransformers/MinSearch dependencies

**File: `rag_agent/tools.py`**
- Replace `search_documents()` with `search_mongodb()`:
  - Accept query string and optional tag filters
  - Construct MongoDB `$text` search query: `{"$text": {"$search": query}, "tags": {"$in": [...]}}`
  - Execute directly against MongoDB
  - Return results with sources in SearchResult format
- Remove global `_search_index` variable
- Remove `initialize_search_index()` function
- Remove SentenceTransformers/MinSearch code
- Tool signature: `search_mongodb(query: str, tags: list[str] | None = None, num_results: int = 5) -> List[SearchResult]`

**File: `rag_agent/config.py`**
- Remove `search_type` (no longer needed - only MongoDB text search)
- Remove SentenceTransformers model config
- Keep MongoDB connection config

**File: `config/instructions.py`**
- Update RAG_AGENT instructions:
  - Remove semantic search references
  - Emphasize MongoDB text search with tag filtering
  - LLM decides which tags to filter by (e.g., "user-behavior", "usability")
  - LLM constructs MongoDB query intelligently
  - Can make multiple queries with different tag combinations if needed

**Key Changes:**
- Direct MongoDB queries: `{"$text": {"$search": query}, "tags": {"$in": [...]}}`
- Agent decides: LLM selects relevant tags and constructs queries
- No embeddings: Fast, simple, uses MongoDB native capabilities
- No pre-loading: Fast initialization, scales to any dataset size

### Step 2: Implement Cypher Agent

**Create: `cypher_agent/__init__.py`**
- Package initialization

**Create: `cypher_agent/config.py`**
- `CypherConfig` class with:
  - `neo4j_uri`, `neo4j_user`, `neo4j_password`
  - `openai_model` (default: gpt-4o-mini)
  - `max_query_attempts` (default: 3)

**Create: `cypher_agent/models.py`**
- `CypherAnswer` model (similar to `RAGAnswer`):
  - `answer: str`
  - `confidence: float`
  - `sources_used: list[str]` (question IDs, user IDs, etc.)
  - `reasoning: str | None`
  - `query_used: str | None` (the Cypher query executed)

**Create: `cypher_agent/tools.py`**
- `execute_cypher_query(query: str) -> dict`:
  - Execute Cypher query against Neo4j
  - Return results as structured dict
  - Handle errors gracefully

**Create: `cypher_agent/agent.py`**
- `CypherAgent` class:
  - `__init__(config: CypherConfig)`
  - `initialize()`: Create Neo4j driver, initialize agent with tools
  - `query(question: str) -> tuple[CypherAnswer, list[dict]]`: Generate Cypher query, execute, return answer
- Use OpenAI model (gpt-4o-mini)
- Tool: `execute_cypher_query`
- Instructions: Generate Cypher queries from natural language

**Neo4j Schema Reference:**
- Nodes: `User`, `Question`, `Answer`, `Comment`, `Tag`
- Relationships: `ASKED`, `ANSWERED`, `HAS_ANSWER`, `HAS_TAG`, `ACCEPTED`, etc.
- Properties: `question_id`, `user_id`, `title`, `body`, `score`, etc.

### Step 3: Update Orchestrator Tools

**File: `orchestrator/tools.py`**
- Update `call_cypher_query_agent()`:
  - Remove placeholder
  - Import and initialize `CypherAgent`
  - Call `cypher_agent.query(question)`
  - Return structured response matching `call_rag_agent()` format
- Add global `_cypher_agent_instance` (similar to `_rag_agent_instance`)
- Add `initialize_cypher_agent()` function

**File: `orchestrator/agent.py`**
- No changes needed (already has both tools)

### Step 4: Clean Up Dependencies

**File: `pyproject.toml`**
- Remove `sentence-transformers` dependency (if not used elsewhere)
- Keep `minsearch` only if needed for other purposes, otherwise remove

**File: `search/` directory**
- Can be removed or kept for reference
- No longer used by MongoDB agent

### Step 5: Update Configuration

**File: `config/instructions.py`**
- Verify `CYPHER_QUERY_AGENT` instructions are complete
- Ensure instructions emphasize:
  - Generate valid Cypher queries
  - Handle Neo4j schema correctly (User, Question, Answer, Comment, Tag nodes)
  - Return structured answers with sources

**File: `config/__init__.py`**
- Remove `DEFAULT_SEARCH_TYPE` (no longer needed)
- Remove `DEFAULT_SENTENCE_TRANSFORMER_MODEL` (no longer needed)
- Add Cypher agent default config if needed

### Step 6: Testing

**Update: `tests/rag_agent/test_agent.py`**
- Update tests for MongoDB text search pattern (no pre-loading, no SearchIndex)
- Test MongoDB queries work
- Test tag filtering
- Remove tests that check for SearchIndex

**Update: `tests/rag_agent/test_tools.py`**
- Update tests for `search_mongodb()` tool
- Test MongoDB query construction
- Test tag filtering

**Create: `tests/cypher_agent/test_agent.py`**
- Test Cypher query generation
- Test query execution
- Test error handling

**Create: `tests/cypher_agent/test_tools.py`**
- Test `execute_cypher_query()` tool
- Test Neo4j connection

### Step 7: Update CLI (Optional)

**File: `cli.py`**
- Add command to test Cypher agent directly
- Update orchestrator command to show both agents working

## Implementation Order

1. **Step 1** (MongoDB refactor) - Fixes performance issue, simplifies architecture, enables scaling
2. **Step 2** (Cypher agent) - Core functionality
3. **Step 3** (Orchestrator update) - Connects everything
4. **Step 4** (Clean up dependencies) - Remove unused code
5. **Step 5** (Configuration) - Ensures instructions are correct
6. **Step 6** (Testing) - Validates implementation
7. **Step 7** (CLI) - User interface

## Success Criteria

- MongoDB agent uses on-demand MongoDB text search (no pre-loading, no embeddings)
- Agent intelligently constructs MongoDB queries and selects tags
- Cypher agent generates and executes Cypher queries correctly
- Orchestrator routes to appropriate agent(s)
- Both agents return structured answers with sources
- System scales to large datasets (no memory limits)
- Evaluation system works as-is (already compatible)
- Ready for Ollama migration (just swap model provider)

## Evaluation Compatibility

✅ **All evaluation infrastructure works as-is:**
- Ground truth format matches (`expected_sources` → `sources_used`)
- Evaluation system signature matches (`(RAGAnswer, list[dict])`)
- Judge LLM compatible (takes RAGAnswer + tool_calls)
- Source metrics compatible (hit_rate, MRR calculation)
- Tests may need minor updates for implementation details

## Future: Ollama Migration

After implementation works with OpenAI:
- Replace `OpenAIChatModel` with Ollama model provider in pydantic-ai
- Update all agent configs to use Ollama
- Test with local models
- No architecture changes needed (same agent pattern)

## Implementation Todos

1. **mongodb-refactor-agent** - Refactor rag_agent/agent.py: Remove pre-loading methods (_load_from_mongodb, _load_documents), remove SearchIndex initialization, remove SentenceTransformers dependencies, keep MongoDB connection only
2. **mongodb-refactor-tools** - Refactor rag_agent/tools.py: Replace search_documents() with search_mongodb() that uses MongoDB native $text search with optional tag filtering, remove global _search_index, remove initialize_search_index(), remove SentenceTransformers/MinSearch code
3. **mongodb-config-update** - Update rag_agent/config.py: Remove search_type and SentenceTransformers model config, keep only MongoDB connection config
4. **mongodb-instructions-update** - Update config/instructions.py RAG_AGENT: Remove semantic search references, emphasize MongoDB text search with tag filtering, LLM decides tags and constructs queries
5. **cypher-agent-package** - Create cypher_agent package: __init__.py, config.py (CypherConfig with Neo4j credentials and OpenAI model), models.py (CypherAnswer model with query_used field)
6. **cypher-agent-tools** - Create cypher_agent/tools.py: Implement execute_cypher_query() function that executes Cypher queries against Neo4j and returns structured results with error handling
7. **cypher-agent-implementation** - Create cypher_agent/agent.py: Implement CypherAgent class with query() method that generates Cypher queries from natural language and executes them, returns (CypherAnswer, tool_calls)
8. **orchestrator-cypher-integration** - Update orchestrator/tools.py: Replace placeholder call_cypher_query_agent() with real implementation that initializes and calls CypherAgent, add global _cypher_agent_instance
9. **cleanup-dependencies** - Update pyproject.toml: Remove sentence-transformers dependency, remove minsearch if not needed, clean up unused search code
10. **cypher-instructions-verify** - Verify config/instructions.py has complete CYPHER_QUERY_AGENT instructions with Neo4j schema details (User, Question, Answer, Comment, Tag nodes) and query generation guidelines
11. **update-rag-tests** - Update tests/rag_agent/: Modify tests for MongoDB text search pattern (no pre-loading, no SearchIndex, test MongoDB queries and tag filtering)
12. **create-cypher-tests** - Create tests/cypher_agent/: Add test_agent.py and test_tools.py to test Cypher query generation and execution
