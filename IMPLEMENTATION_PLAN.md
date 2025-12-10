# Implementation Plan: Remaining Features

## Overview

This plan covers the remaining features to be implemented for the user behavior analysis system.

**Already Completed:**
- ✅ Phase 1: Incremental Storage
- ✅ Phase 2: Logging & Cost Tracking Infrastructure
- ✅ Phase 3: Streamlit UI with streaming support
- ✅ Basic caching optimizations
- ✅ MongoDB Agent: Tool call limit enforcement (hard stop with exception)
- ✅ MongoDB Agent: Counter synchronization fix (thread-safe with Lock)
- ✅ MongoDB Agent: Schema fix (added `searches` field to `SearchAnswer`)
- ✅ MongoDB Agent: Pre-call validation (prevents 4th call from starting)
- ✅ MongoDB Agent: Counter reset verification
- ✅ Performance: Async database logging
- ✅ Performance: Optimize `get_output()` call in streamlit_app.py
- ✅ Performance: Parallel agent execution (`call_both_agents_parallel`)
- ✅ Phase 0: Instruction Improvements - Streamlined and optimized all agent instructions
- ✅ Orchestrator Tools Refactoring - DRY refactoring with AgentManager pattern and comprehensive tests

**Status Update:**
- Phase 0 (Instruction Improvements) is **COMPLETE** - all instructions refactored for efficiency
- Phase 0 (MongoDB Agent Limit Fix) is **COMPLETE** - all fixes implemented and working
- Phase 1 (Performance Optimization) is **MOSTLY COMPLETE** - async logging and parallel execution done
- Orchestrator Tools Refactoring is **COMPLETE** - AgentManager pattern implemented, tests added

**Still To Do:**
1. **Cypher Query Agent**: Full implementation with proper instructions
2. **Evaluation Framework**: For Cypher Query Agent
3. **Guardrails**: Safety and quality controls for agents
4. **Local LLM Support**: Future enhancement for cloud deployment
5. **Structured Routing Log**: Add dedicated routing_log field to OrchestratorAnswer model

---

## Phase 0.5: Orchestrator Tools Refactoring ✅ COMPLETE

**Status:** ✅ **COMPLETE** - Refactored orchestrator tools to eliminate DRY violations

**Summary:**
Refactored `orchestrator/tools.py` to use a generic `AgentManager` pattern that eliminates code duplication between MongoDB and Cypher agent management. Implemented comprehensive unit tests for the refactored code.

**Key Improvements:**
- ✅ Created generic `AgentManager[AgentT, ConfigT, ResultT]` class for agent lifecycle management
- ✅ Eliminated duplicate code between `call_mongodb_agent()` and `call_cypher_query_agent()` functions
- ✅ Implemented lazy initialization with config change detection
- ✅ Added comprehensive unit tests (`tests/orchestrator/test_tools.py`)
- ✅ Updated `conftest.py` to use refactored API
- ✅ Fixed import sorting in `cypher_agent/config.py`

**Files Modified:**
- `orchestrator/tools.py` - Refactored with AgentManager pattern
- `tests/orchestrator/test_tools.py` - New comprehensive test suite (4 tests)
- `tests/orchestrator/conftest.py` - Updated to use `mongodb_manager.initialize()`
- `cypher_agent/config.py` - Fixed import sorting (ruff compliance)

**Implementation Details:**
- `AgentManager` provides generic agent initialization, lifecycle management, and result formatting
- Supports lazy initialization with automatic re-initialization on config changes
- Maintains backward compatibility with existing `call_mongodb_agent()` and `call_cypher_query_agent()` functions
- All tests pass and pre-commit hooks verified

**Commits:**
- `3ec5561` - refactor tools.py in orchestrator (avoid DRY); implement tests for refactored version of tools.py
- `c55d79d` - fix: update conftest.py to use refactored mongodb_manager API

---

## Phase 0: Instruction Improvements ✅ COMPLETE

**Status:** ✅ **COMPLETE** - All instruction improvements implemented and optimized

**Summary:**
Refactored all three agent instruction sets (Orchestrator, MongoDB, Cypher) to reduce verbosity while maintaining effectiveness. Consolidated repetitive warnings, removed redundant explanations, and streamlined error handling. Achieved ~30-40% reduction in instruction length, resulting in lower token costs and faster processing.

**Key Improvements:**
- ✅ Consolidated repetitive warnings into concise statements
- ✅ Removed redundant explanations and over-explained concepts
- ✅ Streamlined error handling scenarios
- ✅ Simplified field constraints and safety rules
- ✅ Condensed answer synthesis instructions
- ✅ Maintained all critical constraints (one call per agent, read-only operations, authoritative results)

**Files Modified:**
- `config/instructions.py` - All three agent instruction sets refactored

### 0.1 MongoDB Agent Instruction Enhancements ✅

**Completed:**
- ✅ Added explicit schema/field constraints with clear warnings
- ✅ Added concrete query examples (5 examples with expected outcomes)
- ✅ Expanded domain-specific rules (tag format, question ID format, score interpretation)
- ✅ Added safety constraints (read-only operation)
- ✅ Enhanced answer synthesis instructions (authoritative results handling)
- ✅ Added query validation guidance

### 0.2 Cypher Agent Instruction Enhancements ✅

**Completed:**
- ✅ Schema injection mechanism (`{schema}` placeholder) - already present
- ✅ Added explicit constraints (schema compliance, response format, query construction)
- ✅ Added concrete Cypher query examples (5 examples)
- ✅ Added domain-specific rules for StackExchange (node labels, relationship types, property formats)
- ✅ Added safety constraints (read-only, data protection, query safety)
- ✅ Added answer synthesis instructions (authoritative results handling)
- ✅ Query validation guidance included

### 0.3 Orchestrator Agent Instruction Enhancements ✅

**Completed:**
- ✅ Enhanced result handling instructions (empty results, contradictory results, partial success)
- ✅ Added explicit "DO NOT" constraints (consolidated into concise rules)
- ✅ Added concrete error handling examples (7 scenarios streamlined to 5)

---

## Phase 1: Cypher Query Agent Implementation

### 1.1 Create Cypher Query Agent Module Structure

**New Files:**
- `cypher_agent/__init__.py` - Module exports
- `cypher_agent/config.py` - Configuration class
- `cypher_agent/models.py` - Data models (CypherAnswer, CypherAgentResult)
- `cypher_agent/agent.py` - Main agent class
- `cypher_agent/tools.py` - Neo4j query execution tool

### 1.2 Implement Neo4j Schema Retrieval

**File:** `cypher_agent/tools.py`

**Function:** `get_neo4j_schema() -> str`
- Connect to Neo4j using `neo4j.GraphDatabase.driver()`
- Query schema: `CALL db.schema.visualization()` or `CALL db.schema.nodeTypeProperties()`
- Format schema as text for injection into prompt
- Cache schema (refresh periodically or on initialization)
- Return formatted string with node labels, relationship types, and properties

### 1.3 Implement Neo4j Connection and Query Execution

**File:** `cypher_agent/tools.py`

**Function:** `execute_cypher_query(query: str) -> dict`
- Use `neo4j.GraphDatabase.driver()` with config from `config/__init__.py`
- Validate query before execution (check for write operations, syntax)
- Execute query and return results as structured data
- Handle query errors gracefully (syntax errors, timeout, connection errors)
- Return format: `{"results": [...], "query": query, "error": None or str}`

**Query Validation:**
- Check for write operations: `CREATE`, `DELETE`, `SET`, `REMOVE`, `MERGE` (with write intent)
- Basic syntax validation (balanced parentheses, brackets)
- Schema validation (check node labels and relationship types exist)

### 1.4 Implement Agent Class

**File:** `cypher_agent/agent.py`

**Structure:**
- `CypherQueryAgent` class (similar to `MongoDBSearchAgent`)
- Initialize with Neo4j connection
- Get schema on initialization and inject into instructions
- Use instructions from `config/instructions.py` (`InstructionType.CYPHER_QUERY_AGENT`)
- Tool: `execute_cypher_query`
- Output type: `CypherAnswer` (with answer, confidence, reasoning, sources_used, query_used)
- Track tool calls similar to MongoDB agent
- Handle errors and return structured results

**Key Methods:**
- `initialize()` - Connect to Neo4j, get schema, create agent
- `query(question: str) -> CypherAgentResult` - Run query and return result
- `_get_schema()` - Retrieve and format Neo4j schema
- `_inject_schema_into_instructions(schema: str) -> str` - Inject schema into prompt

### 1.5 Add Cypher Agent Models

**File:** `cypher_agent/models.py`

**Models:**
- `CypherAnswer`: answer, confidence, reasoning, sources_used (list of node IDs), query_used (the Cypher query)
- `CypherAgentResult`: answer (CypherAnswer), tool_calls (list[dict]), token_usage (TokenUsage)
- Similar structure to `mongodb_agent/models.py`

### 1.6 Update Orchestrator Integration

**File:** `orchestrator/tools.py`

**Changes:**
- Replace placeholder `call_cypher_query_agent()` with real implementation
- Initialize `CypherQueryAgent` instance (similar to MongoDB agent pattern)
- Use global instance pattern (like MongoDB agent)
- Call agent and return structured response
- Handle errors and return appropriate dict format
- Match return format of `call_mongodb_agent()` for consistency

### 1.7 Update Instructions with Schema Injection

**File:** `config/instructions.py`

**Changes:**
- Update `InstructionType.CYPHER_QUERY_AGENT` instructions
- Add `{schema}` placeholder for dynamic schema injection
- Include all improvements from Phase 0.2 (examples, constraints, safety rules)
- Add answer synthesis section

---

## Phase 2: Evaluation Framework for Cypher Agent

### 2.1 Create Ground Truth for Cypher Queries

**New File:** `evals/generate_cypher_ground_truth.py`

- Generate questions that require graph traversal
- Include expected Cypher queries or expected results
- Store in JSON format similar to MongoDB ground truth
- Include questions for: simple queries, relationship traversal, aggregations, pattern detection

### 2.2 Extend Evaluation Framework

**File:** `evals/evaluate.py`

- Add function: `evaluate_cypher_agent(ground_truth_path, agent_query_fn, ...)`
- Evaluate: query correctness, result accuracy, query efficiency
- Use judge for answer quality (reuse existing judge)
- Calculate metrics: query_success_rate, result_accuracy, query_complexity

### 2.3 Add Cypher-Specific Metrics

**New File:** `evals/cypher_metrics.py`

- Function: `validate_cypher_query(query)` - basic syntax validation
- Function: `compare_query_results(expected, actual)` - compare graph results
- Function: `calculate_query_efficiency(query, execution_time)` - performance metric
- Function: `check_query_safety(query)` - ensure no write operations

### 2.4 Update CLI

**File:** `cli.py`

- Add command: `evaluate-cypher-agent` (similar to existing evaluation commands)
- Support ground truth file, output path, judge model options

---

## Phase 3: Integration and Testing

### 3.1 Update Dependencies

**File:** `pyproject.toml`

- Ensure `neo4j` package is listed
- Verify version constraints
- Add any missing dependencies for schema retrieval

### 3.2 Update Docker Compose

**File:** `docker-compose.yml`

- Verify Neo4j service is properly configured
- Ensure all services (MongoDB, Neo4j, PostgreSQL) work together
- Add health checks if needed

### 3.3 Update Documentation

**File:** `README.md`

- Add Cypher Query Agent documentation
- Update architecture diagram
- Document integration with existing agents
- Add examples of Cypher agent queries

### 3.4 Integration Testing

- Test Cypher agent with various query types
- Test orchestrator routing to Cypher agent
- Test evaluation framework for Cypher agent
- Test end-to-end flow with all agents
- Test schema injection and dynamic instructions
- Test error handling (invalid queries, connection failures)

---

## Phase 4: Guardrails Implementation

### 4.1 Create Guardrails Module Structure

**New Files:**
- `guardrails/__init__.py` - Core guardrail infrastructure
- `guardrails/checks.py` - Guardrail check functions
- `guardrails/config.py` - Guardrail configuration

**Core Components:**
- `GuardrailException` class
- `GuardrailFunctionOutput` dataclass
- `run_with_guardrails()` function

### 4.2 Create Guardrail Check Functions

**File:** `guardrails/checks.py`

1. **Input validation guardrail:** Check for prohibited topics
2. **Cost control guardrail:** Monitor token usage or execution time
3. **Output quality guardrail:** Validate output quality after agent completes

### 4.3 Integrate into All Agents

**Files:** `mongodb_agent/agent.py`, `orchestrator/agent.py`, `cypher_agent/agent.py`

- Add optional `guardrails` parameter to `query()` method
- Wrap `self.agent.run()` call in `run_with_guardrails()` if guardrails provided

---

## Phase 5: Local LLM Support (Future Enhancement)

**Note:** This phase will be implemented after the first version is complete.

**Goals:**
- Support local LLM providers (Ollama, Crok)
- Remove dependency on OpenAI API keys
- Enable deployment to Streamlit Cloud without API credentials

**Planned Changes:**
- Create abstraction layer for LLM providers (OpenAI, Ollama, Crok)
- Update agent initialization to support multiple providers
- Add provider selection in config/UI
- Update cost tracking to handle local LLMs (zero cost or different pricing model)
- Update docker-compose to make services optional
- Add local LLM setup instructions

**Files to Modify:**
- `mongodb_agent/agent.py` - support multiple providers
- `orchestrator/agent.py` - support multiple providers
- `cypher_agent/agent.py` - support multiple providers
- `config/__init__.py` - add LLM provider configuration
- `monitoring/agent_logging.py` - handle local LLM cost tracking
- `streamlit_app.py` - add provider selection UI
- `docker-compose.yml` - make services optional or remove

**This phase will be implemented as a separate version/iteration.**

---

## Phase 6: Structured Routing Log Enhancement

### Overview

Currently, the routing log is appended as plain text JSON to the answer text, making it difficult to parse, query, and display. This enhancement adds a dedicated structured `routing_log` field to the `OrchestratorAnswer` model.

### Current State

**Problem:**
- Routing log is mixed into the `answer` string as appended text
- Hard to extract, parse, or query routing decisions
- Cannot easily display routing log separately in UI
- Difficult to validate structure
- Cannot query database by route type for analytics

**Current Implementation:**
- Instructions tell LLM to append routing log as JSON text to answer
- Saved in PostgreSQL `assistant_answer` field (mixed with answer text)
- No structured parsing or display

### 6.1 Add RoutingLog Model

**File:** `orchestrator/models.py`

**Changes:**
- Create new `RoutingLog` Pydantic model with structured fields:
  ```python
  class RoutingLog(BaseModel):
      route: str  # "RAG" | "CYPHER" | "BOTH"
      queries: dict[str, str]  # {"rag": "...", "cypher": "..."}
      tags: list[str] | None
      tool_called: str
      reason: str
      notes: str | None  # For error/fallback notes
  ```
- Add `routing_log: RoutingLog` field to `OrchestratorAnswer` model
- Make it optional initially for backward compatibility: `routing_log: RoutingLog | None = None`

### 6.2 Update Instructions

**File:** `config/instructions.py`

**Changes:**
- Update `InstructionType.ORCHESTRATOR_AGENT` instructions
- Change from: "append routing log as JSON text to answer"
- Change to: "include `routing_log` field in your JSON response with the following structure..."
- Provide clear schema for the routing_log field
- Keep backward compatibility note: "If you cannot provide routing_log, append it to answer text as fallback"

### 6.3 Update Stream Handler

**File:** `stream_handler.py`

**Changes:**
- Add `routing_log_container` parameter to `OrchestratorAnswerHandler.__init__()`
- Add `current_routing_log: dict | None` state tracking
- Implement `on_field_end()` handler for `routing_log` field
- Parse and display routing log in UI as it streams in
- Handle nested object parsing for routing_log structure

### 6.4 Update Streamlit UI

**File:** `streamlit_app.py`

**Changes:**
- Add new sidebar container for routing log display
- Show routing log fields: route, queries, tags, reason, notes
- Format routing log nicely (e.g., collapsible section or table)
- Update `run_agent_stream()` to pass routing_log_container to handler
- Update `OrchestratorAnswer` construction to include routing_log field

### 6.5 Database Enhancement (Optional)

**File:** `monitoring/db.py`

**Changes:**
- Optionally add `routing_route` column to `LLMLog` table for easier querying
- Migration script to add column
- Update logging to extract and save routing_route separately
- Or: Extract routing_log from `raw_json` more easily (already structured)

**Benefits:**
- Query logs by route type: `SELECT * FROM llm_logs WHERE routing_route = 'BOTH'`
- Analytics: Count routes, analyze routing patterns
- Debugging: Filter by routing decisions

### 6.6 Update Tests

**Files:** `tests/orchestrator/test_agent.py`, etc.

**Changes:**
- Update tests to include routing_log field in expected output
- Test routing_log parsing and validation
- Test backward compatibility (when routing_log is None)
- Test UI display of routing_log

### 6.7 Benefits

1. **Structured Data**: Easy to parse, validate, and query
2. **Separation of Concerns**: Answer text is clean, routing log is separate
3. **Analytics**: Query database by route type, analyze routing patterns
4. **Debugging**: Easier to see routing decisions in UI and logs
5. **Validation**: Pydantic validates structure automatically
6. **UI Enhancement**: Can display routing log in dedicated sidebar section

### 6.8 Migration Strategy

1. Make `routing_log` optional initially (`routing_log: RoutingLog | None = None`)
2. Update instructions to prefer structured field, but allow text fallback
3. Update stream handler to handle both formats (structured field or parse from text)
4. Gradually migrate to structured format
5. Once stable, make routing_log required and remove text fallback

### Files to Modify

**New Files:**
- None (adds to existing models)

**Modified Files:**
- `orchestrator/models.py` - Add RoutingLog model and field
- `config/instructions.py` - Update instructions to use structured field
- `stream_handler.py` - Add routing_log parsing
- `streamlit_app.py` - Add UI display for routing log
- `monitoring/db.py` - (Optional) Add routing_route column
- `tests/orchestrator/test_agent.py` - Update tests

---

## File Structure Summary

**New Files:**
- `cypher_agent/__init__.py`
- `cypher_agent/config.py`
- `cypher_agent/models.py`
- `cypher_agent/agent.py`
- `cypher_agent/tools.py`
- `evals/generate_cypher_ground_truth.py`
- `evals/cypher_metrics.py`
- `guardrails/__init__.py`
- `guardrails/checks.py`
- `guardrails/config.py`

**Modified Files:**
- `mongodb_agent/agent.py` (add guardrails support)
- `orchestrator/agent.py` (add guardrails support, parallel execution)
- `cypher_agent/agent.py` (add guardrails support)
- `orchestrator/tools.py` (✅ refactored with AgentManager pattern, implement Cypher agent call, parallel execution)
- `monitoring/agent_logging.py` (async logging - DONE)
- `mongodb_agent/config.py` (reduce max_tool_calls, optimize instructions)
- `config/instructions.py` (improve all agent instructions with examples, constraints, safety rules)
- `streamlit_app.py` (optimize get_output - DONE)
- `cli.py` (add guardrails flags, add evaluation commands)
- `evals/evaluate.py` (extend for Cypher)
- `README.md` (update documentation)
- `tests/orchestrator/test_tools.py` (✅ new comprehensive test suite)
- `tests/orchestrator/conftest.py` (✅ updated for refactored API)
- `cypher_agent/config.py` (✅ fixed import sorting)

---

## Implementation Order

1. ✅ **Phase 0**: Instruction Improvements - **COMPLETE**
2. ✅ **Phase 0.5**: Orchestrator Tools Refactoring - **COMPLETE**
3. **Phase 1**: Cypher Query Agent Implementation (core functionality) - **NEXT**
4. **Phase 2**: Evaluation Framework (quality assurance)
5. **Phase 3**: Integration and Testing (polish and validation)
6. **Phase 4**: Guardrails Implementation (safety and quality controls)
7. **Phase 5**: Local LLM Support (future enhancement)
8. **Phase 6**: Structured Routing Log Enhancement

---

## Key Design Decisions

1. **Schema Injection**: Schema will be retrieved on agent initialization and injected into instructions dynamically
2. **Query Validation**: Two-stage validation - syntax check before execution, then execution with error handling
3. **Error Handling**: Cypher agent should return structured errors, not raise exceptions (similar to MongoDB agent limit handling)
4. **Instruction Format**: Follow reference project pattern - explicit constraints, concrete examples, domain-specific rules
5. **Result Format**: Cypher agent results should match MongoDB agent format for consistency in orchestrator

---

## Notes

- All agents should use the same logging infrastructure
- Streamlit UI should work with both MongoDB and Cypher agents
- Cypher agent should handle query errors gracefully
- Evaluation should be consistent across all agents
- Schema injection must be dynamic (refresh on initialization, cache for performance)
- Query validation is critical for safety (prevent write operations)
- Instructions should be comprehensive but not overly verbose (balance detail with clarity)
- Database should be initialized on first use (PostgreSQL via docker-compose)
- Cost tracking uses `genai-prices` library for accurate pricing (OpenAI only in v1)
- Local development: Users run `docker-compose up` locally, no API keys pushed to Streamlit Cloud
- Future v2: Local LLM support will enable cloud deployment without API credentials

---

## Database Configuration

### PostgreSQL Setup

**Environment Variable:**
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/user_behavior_monitoring
```

**Docker Compose:**
```yaml
postgres:
  image: postgres:15-alpine
  ports:
    - "5432:5432"
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: user_behavior_monitoring
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

---

## Local Development Workflow

1. Start services: `docker-compose up -d` (MongoDB, Neo4j, PostgreSQL)
2. Run Streamlit locally: `streamlit run streamlit_app.py`
3. No API keys needed in Streamlit Cloud (users run locally)
4. Future: With local LLMs, can deploy to Streamlit Cloud without credentials

---

## Related Documentation

- `INCREMENTAL_STORAGE_PLAN.md` - Detailed incremental storage implementation
- `GUARDRAILS_IMPLEMENTATION_PLAN.md` - Guardrails feature (future phase)
- `search_agent_architecture_analysis.md` - MongoDB agent optimization notes
- `PERFORMANCE_OPTIMIZATION_ISSUE.md` - Performance optimization issue and solutions
