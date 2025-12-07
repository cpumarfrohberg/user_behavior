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

**Status Update:**
- Phase 0 (MongoDB Agent Limit Fix) is **COMPLETE** - all fixes implemented and working
- Phase 1 (Performance Optimization) is **MOSTLY COMPLETE** - async logging and parallel execution done

**Still To Do:**
1. **Instruction Improvements**: Enhance agent instructions based on reference project analysis
2. **Cypher Query Agent**: Full implementation with proper instructions
3. **Evaluation Framework**: For Cypher Query Agent
4. **Guardrails**: Safety and quality controls for agents
5. **Local LLM Support**: Future enhancement for cloud deployment

---

## Phase 0: Instruction Improvements (Based on Reference Project Analysis)

### 0.1 MongoDB Agent Instruction Enhancements

**Files:** `config/instructions.py`

**Improvements Needed:**

1. **Add Explicit Schema/Field Constraints**
   - List all available MongoDB fields (title, body, tags, question_id, score, site, collected_at)
   - Explicitly state: "DO NOT search for fields that don't exist"
   - Add field descriptions and usage guidelines

2. **Add Concrete Query Examples**
   - Simple keyword search: `"form abandonment"`
   - Multi-word search: `"user frustration login"`
   - Tag-filtered search: `search_mongodb("confusion", tags=["user-behavior"])`
   - Synonym/alternative search: `"user satisfaction"` (to infer frustrations)
   - Show 4-5 examples with expected outcomes

3. **Expand Domain-Specific Rules**
   - Tag format: Use exact tag names (e.g., "user-behavior", not "user_behavior")
   - Question ID format: "question_12345" (always include "question_" prefix)
   - Score interpretation: Higher scores = more upvotes, but don't assume score = relevance
   - Empty results handling: Try broader terms or remove tag filters

4. **Add Safety Constraints**
   - Explicitly state: "This is a READ-ONLY search operation"
   - "You cannot modify, delete, or insert data"
   - "Do not attempt to construct queries that would modify the database"

5. **Enhance Answer Synthesis Instructions**
   - "The search results are authoritative - you must never doubt them"
   - "If search returns empty results ([]), say 'I don't have information about this topic in the database'"
   - "If search returns results, you MUST provide an answer using those results"
   - Handle edge cases: punctuation in IDs, names with special characters

6. **Add Query Validation Guidance**
   - Query must not be empty
   - Must contain at least one meaningful keyword
   - Must not include special MongoDB operators
   - Tag filters must be valid tag names

### 0.2 Cypher Agent Instruction Enhancements

**Files:** `config/instructions.py`

**Improvements Needed:**

1. **Add Schema Injection Mechanism**
   - Implement `graph.refresh_schema()` or equivalent
   - Inject schema into Cypher generation prompt using `{schema}` placeholder
   - Schema should include: node labels, relationship types, properties

2. **Add Explicit Constraints**
   - "Use only the provided relationship types and properties in the schema"
   - "Do not use any other relationship types or properties that are not provided"
   - "Do not include any explanations or apologies in your responses"
   - "Do not respond to any questions that might ask anything other than constructing a Cypher statement"

3. **Add Concrete Cypher Query Examples (4-5 examples)**
   - Simple query: "Which user has asked the most questions?"
   - Relationship traversal: "What tags are most commonly associated with user-behavior questions?"
   - Aggregation: "What percentage of questions with tag 'user-behavior' have accepted answers?"
   - Pattern detection: "Which users who asked questions about 'frustration' also answered questions about 'satisfaction'?"
   - Complex correlation: "What patterns lead from questions about 'confusion' to questions about 'satisfaction'?"

4. **Add Domain-Specific Rules for StackExchange**
   - Node labels: User, Question, Answer, Comment, Tag
   - Relationship types: ASKED, ANSWERED, COMMENTED, HAS_ANSWER, HAS_COMMENT, HAS_TAG, ACCEPTED
   - Tag name format: Use exact tag names (e.g., "user-behavior")
   - Question/Answer ID formats: question_id, answer_id (integers)
   - NULL handling: Use `IS NULL` or `IS NOT NULL` when analyzing missing properties

5. **Add Safety Constraints**
   - "Do not run any queries that would add to or delete from the database"
   - "Never return embedding properties in your queries"
   - "Never include the statement 'GROUP BY' in your query"
   - "Make sure to alias all statements that follow as WITH statement"
   - "If you need to divide numbers, make sure to filter the denominator to be non zero"

6. **Add Answer Synthesis Instructions**
   - Separate section or explicit rules for transforming graph results to natural language
   - "The provided information is authoritative, you must never doubt it"
   - "If the provided information is empty, say you don't know the answer"
   - "If the information is not empty, you must provide an answer using the results"
   - Handle edge cases: empty arrays, time units, names with punctuation

7. **Add Query Validation**
   - Implement Cypher query validation before execution
   - Catch syntax errors early
   - Validate against schema

### 0.3 Orchestrator Agent Instruction Enhancements

**Files:** `config/instructions.py`

**Improvements Needed:**

1. **Enhance Result Handling Instructions**
   - "If an agent returns empty results or 'I don't know', this is VALID - do not retry or reformulate"
   - "If both agents return results, synthesize them even if they seem contradictory"
   - "If one agent fails and the other succeeds, use the successful result and note the failure in routing log"
   - "Never say 'I don't have information' if any agent returned results - use what you have"

2. **Add More Explicit "DO NOT" Constraints**
   - "DO NOT call the same agent twice with different queries"
   - "DO NOT reformulate queries and retry after receiving results"
   - "DO NOT ignore agent results because they seem incomplete"
   - "DO NOT add explanations about why you chose an agent in the answer field"
   - "DO NOT expose internal routing logic in the final answer"

3. **Add Concrete Error Handling Examples**
   - "If MongoDB agent returns 'limit reached' → This is SUCCESS, synthesize from it"
   - "If Cypher agent returns syntax error → Note in routing log, use MongoDB result if available"
   - "If both agents called and one fails → Use successful result, note failure in 'notes' field"
   - "If only agent called fails → Return error message suggesting user rephrase question"

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
- `orchestrator/tools.py` (implement Cypher agent call, parallel execution)
- `monitoring/agent_logging.py` (async logging - DONE)
- `mongodb_agent/config.py` (reduce max_tool_calls, optimize instructions)
- `config/instructions.py` (improve all agent instructions with examples, constraints, safety rules)
- `streamlit_app.py` (optimize get_output - DONE)
- `cli.py` (add guardrails flags, add evaluation commands)
- `evals/evaluate.py` (extend for Cypher)
- `README.md` (update documentation)

---

## Implementation Order

1. **Phase 0**: Instruction Improvements (can be done in parallel with Phase 1)
2. **Phase 1**: Cypher Query Agent Implementation (core functionality)
3. **Phase 2**: Evaluation Framework (quality assurance)
4. **Phase 3**: Integration and Testing (polish and validation)
5. **Phase 4**: Guardrails Implementation (safety and quality controls)
6. **Phase 5**: Local LLM Support (future enhancement)

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
