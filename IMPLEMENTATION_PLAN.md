# Implementation Plan: Remaining Features

## Overview

This plan covers the remaining features to be implemented for the user behavior analysis system.

**Already Completed:**
- ✅ Phase 1: Incremental Storage
- ✅ Phase 2: Logging & Cost Tracking Infrastructure
- ✅ Phase 3: Streamlit UI with streaming support
- ✅ Basic caching optimizations

**Still To Do:**
1. **Performance Optimization**: Address execution speed bottlenecks (do this first!)
2. **Cypher Query Agent**: Agent that translates prompts to Cypher queries and queries Neo4j
3. **Evaluation**: Framework to evaluate the Cypher Query Agent
4. **Guardrails**: Safety and quality controls for agents
5. **Local LLM Support**: Future enhancement for cloud deployment

---

## Phase 1: Performance Optimization

See `PERFORMANCE_OPTIMIZATION_ISSUE.md` for detailed analysis and solutions.

### 1.1 Quick Wins

**1.1.1 Async Database Logging**
- **File**: `monitoring/agent_logging.py`
- Move database logging to background task using `asyncio.create_task()`
- Don't await logging completion
- **Expected Impact**: ~100-500ms improvement per query

**1.1.2 Optimize `get_output()` Call**
- **File**: `streamlit_app.py`
- Check if we can construct output from handler state instead
- Or cache parsed output during streaming
- Only call `get_output()` if handler parsing failed
- **Expected Impact**: ~50-200ms improvement

**1.1.3 Reduce MongoDB Tool Calls**
- **File**: `mongodb_agent/config.py`, `config/instructions.py`
- Reduce max_tool_calls from 10 to 7
- Improve MongoDB agent instructions to be more decisive
- Optimize search queries to be more targeted
- **Expected Impact**: ~30-40% reduction in MongoDB agent execution time

### 1.2 High Impact Optimizations

**1.2.1 Parallel Agent Execution**
- **Files**: `orchestrator/agent.py`, `orchestrator/tools.py`
- Modify orchestrator to detect when both agents are needed
- Use `asyncio.gather()` to run MongoDB and Cypher agents concurrently
- Combine results after both complete
- **Expected Impact**: ~50% reduction in time when both agents are called

**1.2.2 Optimize Tool Call Strategy**
- **Files**: `mongodb_agent/agent.py`, `config/instructions.py`
- Improve agent instructions to make better initial search decisions
- Use search result quality to decide if more searches needed
- Consider batching multiple searches when possible
- **Expected Impact**: ~20-30% reduction in tool call overhead

### 1.3 Testing and Monitoring

**1.3.1 Add Performance Metrics**
- Log timing for each phase (orchestrator, MongoDB agent, tool calls, etc.)
- Track number of API calls and tool calls
- Monitor database logging time

**1.3.2 Baseline Measurement**
- Measure current execution time for typical queries
- Document metrics before optimizations

**1.3.3 After Each Optimization**
- Measure improvement
- Verify functionality still works
- Check for regressions

---

## Phase 2: Cypher Query Agent Implementation

### 2.1 Create Cypher Query Agent Module

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

### 2.2 Implement Neo4j Connection

**File:** `cypher_agent/tools.py`

- Function: `execute_cypher_query(query: str)` - executes Cypher query on Neo4j
- Use `neo4j.GraphDatabase.driver()` with config from `config/__init__.py`
- Handle query errors gracefully
- Return results as structured data
- Add query validation/sanitization

### 2.3 Implement Agent Class

**File:** `cypher_agent/agent.py`

- Similar structure to `MongoDBSearchAgent`
- Initialize with Neo4j connection
- Use instructions from `config/instructions.py` (`InstructionType.CYPHER_QUERY_AGENT`)
- Tool: `execute_cypher_query`
- Output type: `CypherAnswer` (with answer, confidence, reasoning, sources)
- Track tool calls similar to MongoDB agent

### 2.4 Update Orchestrator

**File:** `orchestrator/tools.py`

- Replace placeholder `call_cypher_query_agent()` with real implementation
- Initialize `CypherQueryAgent` instance (similar to MongoDB agent pattern)
- Call agent and return structured response
- Handle errors and return appropriate dict format

### 2.5 Add Cypher Agent Models

**File:** `cypher_agent/models.py`

- `CypherAnswer`: answer, confidence, reasoning, sources_used, query_used
- `CypherAgentResult`: answer (CypherAnswer), tool_calls (list[dict])
- Similar structure to `mongodb_agent/models.py`

---

## Phase 3: Evaluation Framework for Cypher Agent

### 3.1 Create Ground Truth for Cypher Queries

**New File:** `evals/generate_cypher_ground_truth.py`

- Generate questions that require graph traversal
- Expected Cypher queries or expected results
- Store in JSON format similar to MongoDB ground truth

### 3.2 Extend Evaluation Framework

**File:** `evals/evaluate.py`

- Add function: `evaluate_cypher_agent(ground_truth_path, agent_query_fn, ...)`
- Evaluate: query correctness, result accuracy, query efficiency
- Use judge for answer quality (reuse existing judge)
- Calculate metrics: query_success_rate, result_accuracy, query_complexity

### 3.3 Add Cypher-Specific Metrics

**New File:** `evals/cypher_metrics.py`

- Function: `validate_cypher_query(query)` - basic syntax validation
- Function: `compare_query_results(expected, actual)` - compare graph results
- Function: `calculate_query_efficiency(query, execution_time)` - performance metric

### 3.4 Update CLI

**File:** `cli.py`

- Add command: `evaluate-cypher-agent` (similar to existing evaluation commands)
- Support ground truth file, output path, judge model options

---

## Phase 4: Integration and Testing

### 4.1 Update Dependencies

**File:** `pyproject.toml`

- Ensure all new dependencies are listed
- Add `psycopg2-binary` or `asyncpg` for PostgreSQL
- Update version constraints if needed

### 4.2 Update Docker Compose

**File:** `docker-compose.yml`

- Verify PostgreSQL service is properly configured
- Ensure all services (MongoDB, Neo4j, PostgreSQL) work together
- Add health checks if needed

### 4.3 Update Documentation

**File:** `README.md`

- Add Cypher Query Agent documentation
- Update architecture diagram
- Document integration with existing agents

### 4.4 Integration Testing

- Test Cypher agent with various query types
- Test orchestrator routing to Cypher agent
- Test evaluation framework for Cypher agent
- Test end-to-end flow with all agents

---

## Phase 5: Guardrails Implementation

### 5.1 Create Guardrails Module Structure

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

### 5.2 Create Guardrail Check Functions

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

### 5.3 Create Guardrail Configuration

**File:** `guardrails/config.py`

- `GuardrailConfig` dataclass with enable flags
- Configuration for: input validation, cost control, output quality
- Settings: prohibited topics, max tokens, max time, min confidence

### 5.4 Integrate into MongoDB Agent

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

### 5.5 Integrate into Orchestrator Agent

**File:** `orchestrator/agent.py`

**Changes:**
- Add optional `guardrails` parameter to `query()` method
- Wrap `self.agent.run()` call in `run_with_guardrails()` if guardrails provided
- Update method signature: `async def query(self, question: str, guardrails: list = None) -> OrchestratorAnswer`

### 5.6 Integrate into Cypher Agent

**File:** `cypher_agent/agent.py`

**Changes:**
- Add optional `guardrails` parameter to `query()` method
- Wrap `self.agent.run()` call in `run_with_guardrails()` if guardrails provided
- Similar pattern to MongoDB and Orchestrator agents

### 5.7 Update CLI to Support Guardrails

**File:** `cli.py`

**Changes:**
- Add `--guardrails` flag to agent commands
- Create helper function to build guardrail list from config
- Pass guardrails to agent query methods

### 5.8 Update Tests

**Files:** `tests/mongodb_agent/test_agent.py`, `tests/orchestrator/test_agent.py`

**Test cases:**
- Agent runs successfully without guardrails
- Agent is cancelled when guardrail triggers
- Multiple guardrails can run in parallel
- GuardrailException is properly raised and handled

---

## Phase 6: Local LLM Support (Future Enhancement)

### 6.1 Architecture for Local LLMs

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
- `monitoring/agent_logging.py` (async logging)
- `mongodb_agent/config.py` (reduce max_tool_calls, optimize instructions)
- `config/instructions.py` (improve MongoDB agent instructions)
- `streamlit_app.py` (optimize get_output)
- `cli.py` (add guardrails flags, add evaluation commands)
- `evals/evaluate.py` (extend for Cypher)
- `README.md` (update documentation)

---

## Implementation Order

1. **Phase 1**: Performance Optimization (address execution speed issues - do this first!)
2. **Phase 2**: Cypher Query Agent (core functionality)
3. **Phase 3**: Evaluation Framework (quality assurance)
4. **Phase 4**: Integration and Testing (polish and validation)
5. **Phase 5**: Guardrails Implementation (safety and quality controls)
6. **Phase 6**: Local LLM Support (future enhancement)

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
- **Performance**: Current implementation has performance bottlenecks in sequential agent execution - see Phase 8 and `PERFORMANCE_OPTIMIZATION_ISSUE.md` for optimization strategies

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
