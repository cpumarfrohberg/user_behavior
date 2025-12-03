# Performance Optimization Issue

## Problem
The Streamlit app is extremely slow when executing queries. The streaming UI works correctly, but the underlying agent execution chain takes too long.

## Root Causes Identified

### 1. Sequential Agent Execution Chain
- Orchestrator makes LLM API call to decide routing
- MongoDB agent makes LLM API call to process question
- MongoDB agent makes up to 10 sequential tool calls
- Each tool call requires: LLM decision → MongoDB query → LLM processes results → repeat
- If Cypher agent is called, adds another sequential call

**Impact**: 12+ sequential API calls with network latency on each

### 2. Multiple Sequential LLM API Calls
- Orchestrator: 1 API call
- MongoDB agent: 1 initial call + up to 10 tool-call decision calls = up to 11 calls
- Each API call has network latency (~500ms-2s per call)
- Total: Potentially 12+ sequential API calls

### 3. MongoDB Agent Tool Call Loop
- Each `search_mongodb` tool call triggers:
  1. LLM decides to call tool
  2. MongoDB text search execution
  3. Results returned to LLM
  4. LLM decides if more searches needed
- With max 10 tool calls, this can be 10+ round trips

### 4. No Parallelization
- All operations are sequential
- MongoDB and Cypher agents could run in parallel but don't
- Tool calls within an agent are sequential

### 5. `await result.get_output()` Overhead
- May re-parse/validate structured output after streaming completes
- Could add unnecessary overhead

### 6. Database Logging Operations
- After each agent run: extract messages, calculate costs, insert to PostgreSQL
- Happens synchronously and can add latency

## Current State
- ✅ Streaming UI works correctly
- ✅ Caching implemented (agent, database, queries)
- ✅ Debouncing and batched updates implemented
- ❌ Agent execution chain is the bottleneck

## Proposed Solutions

### Option 1: Parallel Agent Execution (High Impact)
**Goal**: Run MongoDB and Cypher agents in parallel when both are needed

**Implementation**:
- Modify orchestrator to detect when both agents are needed
- Use `asyncio.gather()` to run both agents concurrently
- Combine results after both complete

**Expected Impact**: ~50% reduction in time when both agents are called

### Option 2: Reduce MongoDB Tool Calls (Medium Impact)
**Goal**: Make MongoDB agent more efficient with fewer searches

**Implementation**:
- Improve MongoDB agent instructions to be more decisive
- Reduce max_tool_calls from 10 back to 5-7 (with better instructions)
- Optimize search queries to be more targeted

**Expected Impact**: ~30-40% reduction in MongoDB agent execution time

### Option 3: Optimize Tool Call Strategy (Medium Impact)
**Goal**: Reduce number of LLM decisions needed for tool calls

**Implementation**:
- Batch multiple searches in single tool calls when possible
- Improve agent instructions to make better initial search decisions
- Use search result quality to decide if more searches needed

**Expected Impact**: ~20-30% reduction in tool call overhead

### Option 4: Async Database Logging (Low Impact)
**Goal**: Don't block on database logging

**Implementation**:
- Move database logging to background task
- Use `asyncio.create_task()` to log asynchronously
- Don't await logging completion

**Expected Impact**: ~100-500ms improvement per query

### Option 5: Optimize `get_output()` Call (Low Impact)
**Goal**: Avoid redundant parsing after streaming

**Implementation**:
- Check if we can construct output from handler state instead
- Or cache the parsed output during streaming
- Only call `get_output()` if handler parsing failed

**Expected Impact**: ~50-200ms improvement

## Recommended Approach

**Phase 1 (Quick Wins)**:
1. Implement Option 4 (Async Database Logging) - Easy, low risk
2. Implement Option 5 (Optimize get_output) - Easy, low risk
3. Reduce max_tool_calls to 7 with improved instructions - Easy, medium impact

**Phase 2 (High Impact)**:
1. Implement Option 1 (Parallel Agent Execution) - Medium complexity, high impact
2. Implement Option 3 (Optimize Tool Call Strategy) - Medium complexity, medium impact

**Phase 3 (Fine-tuning)**:
1. Monitor performance after Phase 1 & 2
2. Adjust based on actual usage patterns
3. Consider more advanced optimizations if needed

## Testing Strategy

1. **Baseline Measurement**:
   - Measure current execution time for typical queries
   - Log timing for each phase (orchestrator, MongoDB agent, tool calls, etc.)
   - Document in logs or add timing metrics

2. **After Each Optimization**:
   - Measure improvement
   - Verify functionality still works
   - Check for any regressions

3. **Key Metrics to Track**:
   - Total query time
   - Number of API calls
   - Number of tool calls
   - Time per tool call
   - Database logging time

## Files to Modify

- `orchestrator/agent.py` - Add parallel execution logic
- `orchestrator/tools.py` - Modify to support parallel calls
- `mongodb_agent/agent.py` - Optimize tool call strategy
- `mongodb_agent/config.py` - Adjust max_tool_calls
- `config/instructions.py` - Improve MongoDB agent instructions
- `monitoring/agent_logging.py` - Make logging async
- `streamlit_app.py` - Optimize get_output() usage

## Notes

- The streaming UI is working correctly - the issue is in agent execution
- Caching is already implemented and working
- Focus should be on reducing sequential API calls and parallelizing where possible
- Keep user experience in mind - streaming should still work smoothly
