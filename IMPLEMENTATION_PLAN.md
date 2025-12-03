# Implementation Plan: Incremental Storage, Streamlit UI, Logging, and Cypher Query Agent

## Overview

This plan extends the existing user behavior analysis system with:
1. **Incremental Storage**: Store questions in MongoDB as they're collected (from `INCREMENTAL_STORAGE_PLAN.md`)
2. **Streamlit UI**: Interactive web interface for querying agents
3. **Logging & Cost Tracking**: Track function calls, token usage, and costs
4. **Cypher Query Agent**: Agent that translates prompts to Cypher queries and queries Neo4j
5. **Evaluation**: Framework to evaluate the Cypher Query Agent

---

## Phase 1: Incremental Storage Implementation

### 1.1 Modify `search_questions()` Method

**File:** `stream_stackexchange/collector.py`

**Current behavior:**
- Collects all questions in `all_questions` list
- Returns list at the end
- No storage during collection

**Changes needed:**
1. Change return type from `list[Question]` to `int` (total stored count)
2. Remove `all_questions = []` accumulation
3. Add `total_stored = 0` counter
4. Collect questions per page in `page_questions` list (not accumulating across pages)
5. After processing each page, store immediately:
   - Extract relevant questions from current page
   - Call `self.storage.store_questions(page_questions)` immediately
   - Track `total_stored += stored_count`
   - Print progress: `💾 Stored {stored_count} questions from page {page} (total: {total_stored})`
6. Wrap storage call in try-except per page to continue on errors
7. Update docstring to reflect new behavior

**Code structure:**
```python
def search_questions(...) -> int:  # Changed return type
    total_stored = 0
    for page in range(1, pages + 1):
        try:
            # ... fetch page ...
            # ... validate and extract questions ...

            page_questions = []  # Collect questions for this page only
            relevant_count = 0
            for question_dict in questions:
                if not is_relevant(question_dict):
                    continue
                question = extract_question(question_dict, site, self.api_client)
                if question:
                    page_questions.append(question)
                    relevant_count += 1

            # Store immediately after processing page
            if page_questions:
                try:
                    stored_count = self.storage.store_questions(page_questions)
                    total_stored += stored_count
                    print(f"   💾 Stored {stored_count} questions from page {page} (total: {total_stored})")
                except Exception as e:
                    print(f"   ⚠️  Error storing page {page}: {e}")
                    # Continue to next page even if storage fails
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            continue

    return total_stored  # Return count instead of list
```

### 1.2 Simplify `collect_and_store()` Method

**File:** `stream_stackexchange/collector.py`

**Current behavior:**
- Calls `search_questions()` to get list
- Then stores all at once

**Changes needed:**
1. `search_questions()` now handles storage, so simplify this method
2. Change: `questions = self.search_questions(...)` → `total_stored = self.search_questions(...)`
3. Remove the `if questions:` block that calls `store_questions()`
4. Update final print: `print(f"✅ Total stored: {total_stored} documents")`
5. Update docstring

**Code structure:**
```python
def collect_and_store(...):
    total_stored = self.search_questions(site, tag, pages)  # Already stores as it goes
    if total_stored > 0:
        print(f"✅ Total stored: {total_stored} documents")
    else:
        print("No questions collected")
```

### 1.3 Error Handling Improvements

**File:** `stream_stackexchange/collector.py`

**Changes needed:**
1. Wrap storage call in try-except per page (already in 1.1)
2. Continue to next page if storage fails for one page
3. Log which pages failed with error message
4. Return partial success (count of successfully stored pages)
5. Add error logging: `print(f"⚠️  Error storing page {page}: {e}")`

### 1.4 Progress Messages

**File:** `stream_stackexchange/collector.py`

**Changes needed:**
1. Add storage progress message after each page
2. Show running total: `(total: {total_stored})`
3. Add summary at end with final count
4. Keep existing fetch/validation messages

**New messages:**
- `💾 Stored {count} questions from page {page} (total: {total})`
- `✅ Collection complete: {total} documents stored`

---

## Phase 2: Logging and Cost Tracking Infrastructure

### 2.1 Add Dependencies

**File:** `pyproject.toml`

- Add `genai-prices` for cost calculation
- Add `sqlalchemy` for database ORM
- Add `psycopg2-binary` or `asyncpg` for PostgreSQL support
- Add `jaxn` for streaming JSON parsing (if not already present)

### 2.2 Create Monitoring Database Module

**New File:** `monitoring/__init__.py`
**New File:** `monitoring/db.py`
**New File:** `monitoring/schemas.py`

- Create PostgreSQL database schema using SQLAlchemy
- Tables: `llm_logs`, `eval_checks`, `guardrail_events`
- Functions: `init_db()`, `insert_log()`, `get_recent_logs()`, `get_cost_stats()`
- Pydantic schemas: `LogCreate`, `LogResponse`, `LogSummaryResponse`
- Use PostgreSQL connection string from environment (DATABASE_URL)
- Reference: `~/projects/projects_action/AI_Bootcamp/own/ai-bootcamp-krlz/homework/homework_week4/wikiagent/monitoring/`

### 2.3 Create Agent Logging Module

**New File:** `monitoring/agent_logging.py`

- Function: `save_log_to_db(agent, result, question)` - saves agent run to database
- Function: `_calc_cost(provider, model, input_tokens, output_tokens)` - calculates cost using genai_prices
- Function: `_create_log_entry(agent, messages, usage, output)` - extracts log data
- Function: `_log_agent_run(agent, result)` - unified logging for streaming runs
- Reference: `~/projects/projects_action/AI_Bootcamp/own/ai-bootcamp-krlz/homework/homework_week4/wikiagent/agent_logging.py`

### 2.4 Update Config

**File:** `config/__init__.py`

- Add `DATABASE_URL` environment variable (default: PostgreSQL connection string)
- Default: `postgresql://postgres:postgres@localhost:5432/user_behavior_monitoring`
- Add database initialization on module load

### 2.5 Add PostgreSQL to Docker Compose

**File:** `docker-compose.yml`

- Add PostgreSQL service:
  - Image: `postgres:15-alpine`
  - Ports: `5432:5432`
  - Environment: `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=user_behavior_monitoring`
  - Volumes: `postgres_data:/var/lib/postgresql/data`
- Add `postgres_data` volume

### 2.6 Integrate Logging into Existing Agents

**Files:** `mongodb_agent/agent.py`, `orchestrator/agent.py`

- Import `log_agent_run` from `monitoring.agent_logging`
- After agent query completes, call `await log_agent_run(agent, result, question)`
- Handle errors gracefully (log but don't fail agent execution)

---

## Phase 3: Streamlit UI Implementation

### 3.1 Create Streamlit Application

**New File:** `streamlit_app.py`

**Structure:**
- Navigation sidebar: Chat, Monitoring, About, Settings
- Chat page: Interactive chat interface with streaming responses
- Monitoring page: Cost statistics and recent logs
- Settings page: Configuration options

**Features:**
- Real-time streaming of agent responses
- Tool calls display during execution
- Token usage and cost metrics
- Chat history persistence in session state
- Error handling and user feedback

**Reference:** `~/projects/projects_action/wikipagent/streamlit_app.py` and `~/projects/projects_action/AI_Bootcamp/own/ai-bootcamp-krlz/homework/homework_week4/streamlit_app.py`

### 3.2 Create Stream Handler

**New File:** `stream_handler.py` (or integrate into existing structure)

- Handle streaming JSON parsing for structured output
- Update UI containers in real-time
- Track tool calls and display them

### 3.3 Update CLI to Support Streamlit

**File:** `cli.py`

- Add command: `streamlit run streamlit_app.py` or create wrapper
- Or add to README instructions

---

## Phase 4: Cypher Query Agent Implementation

### 4.1 Create Cypher Query Agent Module

**New File:** `cypher_agent/__init__.py`
**New File:** `cypher_agent/config.py`
**New File:** `cypher_agent/models.py`
**New File:** `cypher_agent/agent.py`
**New File:** `cypher_agent/tools.py`

**Structure:**
- `CypherAgentConfig`: Configuration class (similar to `MongoDBConfig`)
- `CypherAnswer`: Pydantic model for structured output (similar to `SearchAnswer`)
- `CypherAgentResult`: Result model with answer and tool calls
- `CypherQueryAgent`: Main agent class

### 4.2 Implement Neo4j Connection

**File:** `cypher_agent/tools.py`

- Function: `execute_cypher_query(query: str)` - executes Cypher query on Neo4j
- Use `neo4j.GraphDatabase.driver()` with config from `config/__init__.py`
- Handle query errors gracefully
- Return results as structured data
- Add query validation/sanitization

### 4.3 Implement Agent Class

**File:** `cypher_agent/agent.py`

- Similar structure to `MongoDBSearchAgent`
- Initialize with Neo4j connection
- Use instructions from `config/instructions.py` (`InstructionType.CYPHER_QUERY_AGENT`)
- Tool: `execute_cypher_query`
- Output type: `CypherAnswer` (with answer, confidence, reasoning, sources)
- Track tool calls similar to MongoDB agent

### 4.4 Update Orchestrator

**File:** `orchestrator/tools.py`

- Replace placeholder `call_cypher_query_agent()` with real implementation
- Initialize `CypherQueryAgent` instance (similar to MongoDB agent pattern)
- Call agent and return structured response
- Handle errors and return appropriate dict format

### 4.5 Add Cypher Agent Models

**File:** `cypher_agent/models.py`

- `CypherAnswer`: answer, confidence, reasoning, sources_used, query_used
- `CypherAgentResult`: answer (CypherAnswer), tool_calls (list[dict])
- Similar structure to `mongodb_agent/models.py`

---

## Phase 5: Evaluation Framework for Cypher Agent

### 5.1 Create Ground Truth for Cypher Queries

**New File:** `evals/generate_cypher_ground_truth.py`

- Generate questions that require graph traversal
- Expected Cypher queries or expected results
- Store in JSON format similar to MongoDB ground truth

### 5.2 Extend Evaluation Framework

**File:** `evals/evaluate.py`

- Add function: `evaluate_cypher_agent(ground_truth_path, agent_query_fn, ...)`
- Evaluate: query correctness, result accuracy, query efficiency
- Use judge for answer quality (reuse existing judge)
- Calculate metrics: query_success_rate, result_accuracy, query_complexity

### 5.3 Add Cypher-Specific Metrics

**New File:** `evals/cypher_metrics.py`

- Function: `validate_cypher_query(query)` - basic syntax validation
- Function: `compare_query_results(expected, actual)` - compare graph results
- Function: `calculate_query_efficiency(query, execution_time)` - performance metric

### 5.4 Update CLI

**File:** `cli.py`

- Add command: `evaluate-cypher-agent` (similar to existing evaluation commands)
- Support ground truth file, output path, judge model options

---

## Phase 6: Integration and Testing

### 6.1 Update Dependencies

**File:** `pyproject.toml`

- Ensure all new dependencies are listed
- Add `psycopg2-binary` or `asyncpg` for PostgreSQL
- Update version constraints if needed

### 6.2 Update Docker Compose

**File:** `docker-compose.yml`

- Verify PostgreSQL service is properly configured
- Ensure all services (MongoDB, Neo4j, PostgreSQL) work together
- Add health checks if needed

### 6.3 Update Documentation

**File:** `README.md`

- Add Streamlit UI usage instructions
- Add Cypher Query Agent documentation
- Add monitoring/logging section
- Update architecture diagram
- Add PostgreSQL setup instructions
- Document local development workflow (no API keys in cloud)

### 6.4 Integration Testing

- Test incremental storage with small page count
- Test Streamlit UI with all agents
- Test logging captures all agent runs
- Test Cypher agent with various query types
- Test evaluation framework
- Test PostgreSQL connection and persistence

---

## Phase 7: Guardrails Implementation

### 7.1 Create Guardrails Module Structure

**New File:** `guardrails/__init__.py`
**New File:** `guardrails/checks.py`
**New File:** `guardrails/config.py`

**Core Components:**
- `GuardrailException` class (custom exception for guardrail failures)
- `GuardrailFunctionOutput` dataclass (output structure for guardrails)
- `run_with_guardrails()` function (main orchestration function)

**Key code:**
```python
# guardrails/__init__.py
from dataclasses import dataclass
import asyncio

@dataclass
class GuardrailFunctionOutput:
    output_info: str
    tripwire_triggered: bool

class GuardrailException(Exception):
    def __init__(self, message: str, info: GuardrailFunctionOutput):
        super().__init__(message)
        self.info = info

async def run_with_guardrails(agent_coroutine, guardrails):
    """
    Run agent_coroutine while multiple guardrails monitor it.
    If any guardrail triggers, cancels the agent and raises GuardrailException.
    """
    agent_task = asyncio.create_task(agent_coroutine)
    guard_tasks = [asyncio.create_task(g) for g in guardrails]

    try:
        await asyncio.gather(agent_task, *guard_tasks)
        return agent_task.result()
    except GuardrailException as e:
        print("[guardrail fired]", e.info)
        agent_task.cancel()
        for t in guard_tasks:
            t.cancel()
        await asyncio.gather(*guard_tasks, return_exceptions=True)
        raise
```

### 7.2 Create Guardrail Check Functions

**File:** `guardrails/checks.py`

**Implementations:**
1. **Input validation guardrail:**
   - Check for prohibited topics in user input
   - Raises `GuardrailException` if prohibited topic found

2. **Cost control guardrail:**
   - Monitor token usage or execution time
   - Raises `GuardrailException` if limits exceeded

3. **Output quality guardrail:**
   - Validate output quality after agent completes
   - Checks confidence threshold if available
   - Raises `GuardrailException` if quality too low

### 7.3 Create Guardrail Configuration

**File:** `guardrails/config.py`

- `GuardrailConfig` dataclass with enable flags
- Configuration for: input validation, cost control, output quality
- Settings: prohibited topics, max tokens, max time, min confidence

### 7.4 Integrate into MongoDB Agent

**File:** `mongodb_agent/agent.py`

**Changes:**
- Add optional `guardrails` parameter to `query()` method
- Wrap `self.agent.run()` call in `run_with_guardrails()` if guardrails provided
- Update method signature: `async def query(self, question: str, guardrails: list = None) -> SearchAgentResult`

**Integration point:**
```python
# In query() method, replace:
result = await self.agent.run(question, event_stream_handler=track_tool_calls)

# With:
agent_coroutine = self.agent.run(question, event_stream_handler=track_tool_calls)
if guardrails:
    result = await run_with_guardrails(agent_coroutine, guardrails)
else:
    result = await agent_coroutine
```

### 7.5 Integrate into Orchestrator Agent

**File:** `orchestrator/agent.py`

**Changes:**
- Add optional `guardrails` parameter to `query()` method
- Wrap `self.agent.run()` call in `run_with_guardrails()` if guardrails provided
- Update method signature: `async def query(self, question: str, guardrails: list = None) -> OrchestratorAnswer`

### 7.6 Integrate into Cypher Agent

**File:** `cypher_agent/agent.py`

**Changes:**
- Add optional `guardrails` parameter to `query()` method
- Wrap `self.agent.run()` call in `run_with_guardrails()` if guardrails provided
- Similar pattern to MongoDB and Orchestrator agents

### 7.7 Update CLI to Support Guardrails

**File:** `cli.py`

**Changes:**
- Add `--guardrails` flag to agent commands
- Create helper function to build guardrail list from config
- Pass guardrails to agent query methods

### 7.8 Update Tests

**Files:** `tests/mongodb_agent/test_agent.py`, `tests/orchestrator/test_agent.py`

**Test cases:**
- Agent runs successfully without guardrails
- Agent is cancelled when guardrail triggers
- Multiple guardrails can run in parallel
- GuardrailException is properly raised and handled

---

## Phase 8: Future - Local LLM Support (Post-MVP)

### 8.1 Architecture for Local LLMs

**Note:** This phase will be implemented after the first version is complete.

**Goals:**
- Support local LLM providers (Ollama, Crok)
- Remove dependency on OpenAI API keys
- Enable deployment to Streamlit Cloud without API credentials
- Remove Docker requirement (services can run locally or use managed services)

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
- `streamlit_app.py`
- `stream_handler.py` (or integrate into existing)
- `monitoring/__init__.py`
- `monitoring/db.py`
- `monitoring/schemas.py`
- `monitoring/agent_logging.py`
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
- `stream_stackexchange/collector.py` (incremental storage)
- `mongodb_agent/agent.py` (add logging, add guardrails support)
- `orchestrator/agent.py` (add logging, add guardrails support)
- `cypher_agent/agent.py` (add guardrails support)
- `orchestrator/tools.py` (implement Cypher agent call)
- `cli.py` (add guardrails flags, add evaluation commands)
- `config/__init__.py` (add DATABASE_URL)
- `pyproject.toml` (add dependencies)
- `docker-compose.yml` (add PostgreSQL)
- `evals/evaluate.py` (extend for Cypher)
- `README.md` (update documentation)

---

## Implementation Order

1. **Phase 1**: Incremental Storage (quick win, unblocks data collection)
2. **Phase 2**: Logging Infrastructure (foundation for monitoring)
3. **Phase 3**: Streamlit UI (user-facing interface)
4. **Phase 4**: Cypher Query Agent (core functionality)
5. **Phase 5**: Evaluation Framework (quality assurance)
6. **Phase 6**: Integration and Testing (polish and validation)
7. **Phase 7**: Guardrails Implementation (safety and quality controls)
8. **Phase 8**: Local LLM Support (future enhancement)

---

## Notes

- All agents should use the same logging infrastructure
- Streamlit UI should work with both MongoDB and Cypher agents
- Cypher agent should handle query errors gracefully
- Evaluation should be consistent across all agents
- Database should be initialized on first use (PostgreSQL via docker-compose)
- Cost tracking uses `genai-prices` library for accurate pricing (OpenAI only in v1)
- Local development: Users run `docker-compose up` locally, no API keys pushed to Streamlit Cloud
- Future v2: Local LLM support will enable cloud deployment without API credentials
- Guardrails implementation is included as Phase 7 with full integration into all agents

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
