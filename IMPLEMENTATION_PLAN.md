# Adapt Project to New Architecture and Evaluation Pattern

## Overview
Refactor the current project to:
1. Match the target architecture (Three-Agent + Judge System with Orchestrator)
2. Implement the Wikipedia agent evaluation pattern for all agents
3. Create StackExchange API agent (similar to Wikipedia agent)
4. Refactor MongoDB agent to use on-demand queries (not pre-loading)
5. Update evaluation system to match homework_week3 pattern

## Current State Analysis

### Existing Components
- **Orchestrator Agent** (`orchestrator/agent.py`) - Routes to RAG and Cypher agents
- **RAG Agent** (`rag_agent/agent.py`) - Pre-loads MongoDB documents into in-memory index
- **Evaluation System** (`evals/`) - Uses CSV format, different from Wikipedia pattern
- **Ground Truth** (`evals/ground_truth.json`) - Exists but format may need updating

### Target Architecture (from agent_architecture_summary.md)
- **MongoDB Query Agent** - On-demand MongoDB queries (not pre-loading)
- **StackExchange API Agent** - Live API calls (like Wikipedia agent)
- **Cypher Query Agent** - Neo4j graph queries
- **Judge Agent** - LLM evaluation
- **Orchestrator Agent** - Routes to appropriate agents

### Evaluation Pattern (from homework_week3)
- `evaluate.py` - Main evaluation runner
- `judge.py` - LLM-as-a-Judge
- `source_metrics.py` - Hit rate and MRR calculation
- `combined_score.py` - Combined scoring formula
- `save_results.py` - JSON output format

## Implementation Plan

### Phase 1: Create StackExchange API Agent (Reference Implementation)

**Files to create:**
- `stackexchange_agent/agent.py` - Main agent (similar to `wikiagent/wikipagent.py`)
- `stackexchange_agent/tools.py` - API tools (similar to `wikiagent/tools.py`)
- `stackexchange_agent/models.py` - Pydantic models (reuse from wikiagent pattern)
- `stackexchange_agent/config.py` - Configuration

**Key changes:**
- Implement `query_stackexchange()` function similar to `query_wikipedia()`
- Create `stackexchange_search()` and `stackexchange_get_question()` tools
- Use StackExchange API (similar to Wikipedia API pattern)
- Track tool calls for evaluation
- Return `StackExchangeAgentResponse` with answer, tool_calls, and usage

**Reference:** `~/projects/projects_action/AI_Bootcamp/own/ai-bootcamp-krlz/homework/homework_week3/wikiagent/`

### Phase 2: Refactor MongoDB Agent (On-Demand Queries)

**Files to modify:**
- `rag_agent/agent.py` - Remove pre-loading, add on-demand MongoDB queries
- `rag_agent/tools.py` - Replace in-memory search with MongoDB queries
- `rag_agent/config.py` - Update configuration

**Key changes:**
- Remove `_load_from_mongodb()` and `_load_documents()` methods
- Remove `SearchIndex` initialization and pre-loading
- Add `mongodb_search()` tool that queries MongoDB directly
- Use MongoDB text search or aggregation pipelines
- Keep tool call tracking for evaluation
- Match Wikipedia agent pattern (async function, tool calls, usage tracking)

**Reference:** `search_agent_architecture_analysis.md` recommends on-demand queries

### Phase 3: Update Models to Match Wikipedia Pattern

**Files to modify:**
- `rag_agent/models.py` - Update to match `wikiagent/models.py`
- `orchestrator/models.py` - May need updates

**Key changes:**
- Rename `RAGAnswer` to `SearchAgentAnswer` (or keep both for compatibility)
- Add `TokenUsage` model
- Add `AgentResponse` wrapper (answer, tool_calls, usage)
- Ensure `sources_used` format matches evaluation expectations

**Reference:** `~/projects/projects_action/AI_Bootcamp/own/ai-bootcamp-krlz/homework/homework_week3/wikiagent/models.py`

### Phase 4: Implement Evaluation System (Wikipedia Pattern) ✅ COMPLETE

**Files created:**
- ✅ `evals/evaluate.py` - Main evaluation runner (similar to homework_week3)
- ✅ `evals/judge.py` - LLM-as-a-Judge (copy from homework_week3)
- ✅ `evals/source_metrics.py` - Hit rate and MRR (copy from homework_week3)
- ✅ `evals/combined_score.py` - Combined scoring (copy from homework_week3)

**Files updated:**
- ✅ `evals/save_results.py` - Added `save_evaluation_results()` function for JSON format
- ✅ `evals/ground_truth.json` - Updated format to include `expected_sources` array
- ✅ `config/__init__.py` - Added `DEFAULT_SCORE_GAMMA = 1.5`
- ✅ `config/instructions.py` - Added `InstructionType.JUDGE` and judge instructions
- ✅ `rag_agent/models.py` - Added `TokenUsage`, `JudgeEvaluation`, `JudgeResult` models

**Key changes completed:**
- ✅ Created `evaluate_agent()` async function that:
  - Loads ground truth
  - Runs agent query for each question (takes agent_query_fn as parameter)
  - Calculates source metrics (hit_rate, MRR)
  - Runs judge evaluation
  - Counts tokens (currently only judge tokens; agent tokens will be added when agents track usage)
  - Calculates combined score
  - Saves results as JSON
- ✅ Updated ground truth format: `{"question": "...", "expected_sources": ["source1", "source2"]}`
- ✅ Evaluation system ready for use with agents

**Reference:** `~/projects/projects_action/AI_Bootcamp/own/ai-bootcamp-krlz/homework/homework_week3/evals/`

**Status:** Phase 4 is 100% complete. Evaluation infrastructure is ready.

### Phase 5: Update Configuration and Instructions

**Files to update:**
- `config/instructions.py` - Add StackExchange agent instructions
- Update existing agent instructions to match Wikipedia pattern
- Add judge instructions (if not present)

**Key changes:**
- Add `STACKEXCHANGE_AGENT` instruction type
- Update `RAG_AGENT` instructions to match Wikipedia agent pattern
- Ensure all instructions emphasize JSON-only output format

**Reference:** `~/projects/projects_action/AI_Bootcamp/own/ai-bootcamp-krlz/homework/homework_week3/config/instructions.py`

### Phase 6: Update Orchestrator

**Files to update:**
- `orchestrator/tools.py` - Add StackExchange agent tool
- `orchestrator/agent.py` - May need minor updates

**Key changes:**
- Add `call_stackexchange_agent()` tool function
- Update orchestrator to route to StackExchange agent when appropriate
- Keep existing MongoDB and Cypher agent tools

### Phase 7: Update Tests

**Files to update:**
- `tests/rag_agent/test_agent.py` - Update for new MongoDB agent pattern
- `tests/rag_agent/test_tools.py` - Update for MongoDB query tools
- Create `tests/stackexchange_agent/` - New tests for StackExchange agent

**Key changes:**
- Test on-demand MongoDB queries (not pre-loading)
- Test StackExchange API tools
- Test evaluation system components

### Phase 8: FastAPI Backend Setup

**Files to create:**
- `api/__init__.py` - API package initialization
- `api/app.py` - FastAPI application with endpoints
- `api/routes.py` - API route handlers (optional, can be in app.py)
- `api/models.py` - API request/response models (Pydantic schemas)

**Key changes:**
- Create FastAPI app with endpoints:
  - `POST /api/query` - Query orchestrator agent
  - `POST /api/query/mongodb` - Query MongoDB agent directly
  - `POST /api/query/stackexchange` - Query StackExchange agent directly
  - `POST /api/query/cypher` - Query Cypher agent directly
  - `GET /api/health` - Health check endpoint
- Use async/await for agent calls
- Return structured JSON responses with answer, sources, tool_calls, usage
- Handle errors gracefully with proper HTTP status codes
- Add CORS middleware for Streamlit frontend
- Add request validation using Pydantic models

**Reference:** Standard FastAPI patterns, async endpoint handlers

### Phase 9: Streamlit Frontend Setup

**Files to create:**
- `ui/__init__.py` - UI package initialization
- `ui/dashboard.py` - Main Streamlit dashboard application
- `ui/components.py` - Reusable Streamlit components (optional)

**Key changes:**
- Create Streamlit app with:
  - Question input form
  - Agent selection (Orchestrator, MongoDB, StackExchange, Cypher)
  - Real-time query execution (calls FastAPI backend)
  - Display answer, confidence, sources
  - Show tool calls and usage metrics
  - Display agent routing decisions (for orchestrator)
  - Error handling and loading states
- Use FastAPI client to call backend endpoints
- Display results in a user-friendly format
- Show metadata (tokens used, agents used, etc.)

**Reference:** Standard Streamlit patterns, FastAPI client integration

### Phase 10: Cleanup and Migration

**Files to delete/archive:**
- `search/` directory - May no longer be needed (in-memory search replaced)
- Old evaluation CSV files - Replace with JSON format
- Unused MongoDB pre-loading code

**Files to update:**
- `cli.py` - Update CLI commands for new evaluation system
- `README.md` - Update documentation with FastAPI and Streamlit usage
- `docker-compose.yml` - Add FastAPI and Streamlit services (if needed)

## Implementation Order

1. ✅ **Phase 4** (Evaluation System) - Set up evaluation infrastructure first - **COMPLETE**
2. **Phase 1** (StackExchange Agent) - Create reference implementation - **NEXT**
3. **Phase 2** (MongoDB Agent Refactor) - Update to on-demand queries
4. **Phase 3** (Models Update) - Align models across agents (partially done in Phase 4)
5. **Phase 5** (Configuration) - Update instructions (partially done in Phase 4)
6. **Phase 6** (Orchestrator) - Integrate new agents
7. **Phase 7** (Tests) - Update and add tests
8. **Phase 8** (FastAPI Backend) - Create API layer for agent calls
9. **Phase 9** (Streamlit Frontend) - Create UI for user interaction
10. **Phase 10** (Cleanup) - Remove old code

## Current Status

**Completed:**
- ✅ Phase 4: Evaluation System (100% complete)
  - All evaluation files created
  - Config and models updated
  - Ground truth format updated

**Next Steps:**
- Phase 1: Create StackExchange API Agent
  - Create `stackexchange_agent/` directory
  - Implement `query_stackexchange()` function
  - Create StackExchange API tools
  - Follow Wikipedia agent pattern

## Key Design Decisions

1. **StackExchange Agent for Evaluation**: Use StackExchange API (like Wikipedia) for evaluation, MongoDB for production
2. **On-Demand MongoDB Queries**: Replace pre-loading with direct MongoDB queries (fixes performance issues)
3. **Unified Evaluation Pattern**: All agents use the same evaluation pattern as Wikipedia agent
4. **JSON-Only Output**: All agents return JSON-only (no markdown, no explanatory text)
5. **Tool Call Tracking**: All agents track tool calls for evaluation

## Success Criteria

- StackExchange agent works like Wikipedia agent (API calls, tool tracking)
- MongoDB agent uses on-demand queries (no pre-loading)
- Evaluation system matches homework_week3 pattern (JSON output, judge, combined score)
- All agents can be evaluated using the same evaluation framework
- Orchestrator routes to appropriate agents
- FastAPI backend exposes all agents via REST endpoints
- Streamlit frontend provides user-friendly interface for querying agents
- Tests pass for all agents

## Implementation Todos

1. ✅ **eval-system** - Implement evaluation system (evaluate.py, judge.py, source_metrics.py, combined_score.py) matching homework_week3 pattern - **COMPLETE**
2. **stackexchange-agent** - Create StackExchange API agent (agent.py, tools.py, models.py, config.py) following Wikipedia agent pattern (depends on: eval-system) - **NEXT**
3. **mongodb-refactor** - Refactor MongoDB agent to use on-demand queries instead of pre-loading (remove SearchIndex, add MongoDB query tools) (depends on: eval-system)
4. ✅ **models-update** - Update models to match Wikipedia agent pattern (TokenUsage, JudgeEvaluation, JudgeResult) - **COMPLETE** (partially)
5. ✅ **config-instructions** - Update configuration and instructions to match Wikipedia agent pattern (JSON-only output, judge instructions) - **COMPLETE** (partially)
6. **orchestrator-update** - Update orchestrator to include StackExchange agent tool and route appropriately (depends on: stackexchange-agent, mongodb-refactor)
7. ✅ **ground-truth-update** - Update ground truth format to include expected_sources array for evaluation - **COMPLETE**
8. **tests-update** - Update tests for new agent patterns and add StackExchange agent tests (depends on: stackexchange-agent, mongodb-refactor)
9. **fastapi-backend** - Create FastAPI backend with endpoints for all agents (depends on: orchestrator-update)
10. **streamlit-frontend** - Create Streamlit frontend for user interaction (depends on: fastapi-backend)
11. **cleanup** - Remove old code (search/ directory, CSV evaluation files, pre-loading code) (depends on: mongodb-refactor, eval-system)
