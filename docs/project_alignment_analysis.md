# Project Alignment Analysis: User Behavior vs Wikipedia Agent

## Executive Summary

This document compares the current **User Behavior** project with the **Wikipedia Agent** project (`homework_week3`) and identifies what needs to change to align the User Behavior project with the Wikipedia Agent's evaluation and testing approach, especially regarding:
- Testing of search agent
- Ground truth implementation
- Judge LLM implementation
- Removing RAG-specific modules

## Key Differences

### 1. **Architecture Philosophy**

**Wikipedia Agent (Reference):**
- **Pure Search Agent**: Searches external API (Wikipedia) → Retrieves pages → Answers questions
- **No RAG**: No document chunking, no vector embeddings, no local index
- **Simple Tools**: `wikipedia_search` (API call) + `wikipedia_get_page` (API call)
- **Evaluation Focus**: Judge LLM + Source metrics (hit rate, MRR)

**User Behavior (Current):**
- **RAG System**: Loads documents from MongoDB → Chunks them → Creates vector index → Searches locally
- **Complex Pipeline**: MongoDB → Chunking → Vector Search (SentenceTransformers) or Text Search (MinSearch)
- **Multiple Agents**: RAG Agent + Orchestrator Agent + Cypher Query Agent
- **Evaluation Focus**: Chunking parameter optimization (grid search)

### 2. **Search Agent Concept**

**Wikipedia Agent:**
- Agent searches **external API** (Wikipedia)
- Agent makes **multiple API calls** to find and retrieve information
- Agent coordinates: search → get page → search again → get another page
- **Makes sense**: Agent orchestrates external API calls

**User Behavior:**
- Agent searches **local MongoDB database** (pre-loaded documents)
- Agent makes **multiple searches** against local vector/text index
- Agent coordinates: search → search again with different query → synthesize
- **Questionable**: Is an agent needed for local database queries?

## Detailed Comparison

### Module Structure

#### Wikipedia Agent (Reference)
```
wikiagent/
  ├── wikipagent.py      # Main agent (query_wikipedia function)
  ├── tools.py            # wikipedia_search, wikipedia_get_page (API calls)
  ├── models.py          # SearchAgentAnswer, WikipediaSearchResult, etc.
  └── config.py          # Agent configuration

evals/
  ├── evaluate.py         # Main evaluation runner
  ├── judge.py            # LLM-as-a-Judge implementation
  ├── source_metrics.py   # Hit rate, MRR calculation
  ├── combined_score.py   # Combined scoring formula
  ├── ground_truth.json   # Questions + expected_sources
  └── save_results.py     # Save evaluation results

tests/
  └── wikiagent/
      ├── test_agent.py   # Agent functional tests
      ├── test_judge.py   # Judge evaluation tests
      └── test_tools.py   # Tool function tests
```

#### User Behavior (Current)
```
rag_agent/
  ├── agent.py            # RAGAgent class (loads MongoDB, chunks, creates index)
  ├── tools.py            # search_documents (searches local index)
  ├── models.py           # RAGAnswer, SearchResult
  └── config.py           # RAGConfig (chunking params, etc.)

orchestrator/            # ⚠️ RAG-specific, not needed for search agent
  ├── agent.py
  ├── tools.py
  └── config.py

search/                   # ⚠️ RAG-specific (chunking, vector search)
  ├── search_utils.py     # SearchIndex class
  ├── simple_chunking.py  # Document chunking
  └── flexible_search.py # Vector/text search

evals/
  ├── generate_ground_truth.py  # Generates from MongoDB (different format)
  ├── ground_truth.json         # Only question + source (no expected_sources)
  └── save_results.py           # Saves chunking evaluation results (CSV)

tests/
  └── rag_agent/
      ├── test_agent.py   # Basic functional tests (no judge, no source metrics)
      └── test_tools.py  # Tool tests
```

## Required Changes

### 1. **Rename/Refactor: RAG Agent → Search Agent**

**Current State:**
- `rag_agent/` module is actually a **search agent** that queries MongoDB
- It's called "RAG" but it's really just searching a local database

**Action:**
- Rename `rag_agent/` → `search_agent/` (or keep name but clarify it's a search agent)
- Update all imports and references
- Update documentation to clarify: "Search Agent that queries MongoDB"

### 2. **Remove RAG-Specific Modules**

**Modules to Remove/Deprecate:**
- `orchestrator/` - Not needed for pure search agent evaluation
- `neo4j_etl/` - Not relevant to search agent testing
- `stream_stackexchange/` - Data ingestion, not part of search agent evaluation

**Modules to Keep but Simplify:**
- `search/` - Keep but simplify (remove chunking if not needed, or make it optional)
- `rag_agent/` → `search_agent/` - Keep but remove RAG-specific terminology

### 3. **Implement Judge LLM**

**Missing:**
- `evals/judge.py` - LLM-as-a-Judge implementation
- Judge evaluation in tests
- Judge integration in evaluation workflow

**Action:**
- Create `evals/judge.py` similar to Wikipedia Agent
- Implement `evaluate_answer()` function
- Add `JudgeEvaluation` and `JudgeResult` models
- Integrate judge into evaluation workflow

### 4. **Update Ground Truth Format**

**Current Format:**
```json
{
  "question": "What are common user behavior patterns?",
  "source": "question_123"
}
```

**Required Format (Wikipedia Agent style):**
```json
{
  "question": "What are common user behavior patterns?",
  "source": "question_123",
  "expected_sources": ["question_123", "question_456", "question_789"]
}
```

**Action:**
- Update `generate_ground_truth.py` to include `expected_sources`
- Manually curate expected sources for each question
- Update ground truth JSON files

### 5. **Implement Source Metrics**

**Missing:**
- `evals/source_metrics.py` - Hit rate and MRR calculation
- Integration into evaluation workflow

**Action:**
- Create `evals/source_metrics.py` with:
  - `calculate_hit_rate(expected_sources, actual_sources)`
  - `calculate_mrr(expected_sources, actual_sources)`
- Integrate into evaluation workflow

### 6. **Implement Combined Score**

**Missing:**
- `evals/combined_score.py` - Combined scoring formula
- Integration into evaluation results

**Action:**
- Create `evals/combined_score.py` with:
  - `calculate_combined_score(hit_rate, judge_score, num_tokens)`
- Formula: `(hit_rate^2.0 * judge_score^1.5) / (num_tokens/1000)^0.5`

### 7. **Update Evaluation Workflow**

**Current:**
- `evaluate_chunking` - Grid search for chunking parameters
- Output: CSV with chunking parameter results

**Required:**
- `evaluate_agent` - Full evaluation workflow (like Wikipedia Agent)
- Output: JSON with hit rate, MRR, judge score, combined score per question

**Action:**
- Create `evals/evaluate.py` similar to Wikipedia Agent
- Run agent query → Calculate source metrics → Run judge → Calculate combined score
- Save results in JSON format with metadata

### 8. **Update Tests**

**Current Tests:**
- Basic functional tests (tool calls, output structure)
- No judge tests
- No source metrics tests
- No evaluation workflow tests

**Required Tests:**
- `test_agent.py` - Similar to Wikipedia Agent (tool invocation, multiple searches)
- `test_judge.py` - Judge evaluation tests
- `test_tools.py` - Tool function tests

**Action:**
- Update `tests/search_agent/test_agent.py` to match Wikipedia Agent style
- Create `tests/search_agent/test_judge.py`
- Update `tests/search_agent/test_tools.py`

### 9. **Update Models**

**Current:**
- `RAGAnswer` - Answer model
- `SearchResult` - Search result model

**Required:**
- `SearchAgentAnswer` - Rename from RAGAnswer (or keep RAGAnswer but clarify)
- `JudgeEvaluation` - Judge output model
- `JudgeResult` - Judge result with usage
- `TokenUsage` - Token usage model
- `SearchAgentResponse` - Response with answer, tool_calls, usage

**Action:**
- Add missing models to `search_agent/models.py`
- Update existing models to match Wikipedia Agent structure

### 10. **Update CLI**

**Current:**
- `agent-ask` - Ask question via RAG agent
- `orchestrator-ask` - Ask via orchestrator
- `generate-ground-truth` - Generate ground truth
- `evaluate-chunking` - Evaluate chunking parameters

**Required:**
- `search-ask` - Ask question via search agent (rename from agent-ask)
- `judge` - Evaluate answer with judge
- `evaluate` - Run full evaluation workflow
- Remove `orchestrator-ask` (not needed for search agent)
- Keep `generate-ground-truth` but update format

**Action:**
- Update CLI commands to match Wikipedia Agent style
- Add `judge` command
- Add `evaluate` command
- Remove orchestrator-related commands

## Evaluation: Does a Search Agent Make Sense?

### Context: MongoDB vs Wikipedia API

**Wikipedia Agent:**
- ✅ **Makes sense**: Agent orchestrates **external API calls**
  - Agent decides: "Search for X" → "Get page Y" → "Search for Z" → "Get page W"
  - Agent coordinates multiple API calls
  - Agent adapts search strategy based on results

**User Behavior (MongoDB):**
- ⚠️ **Questionable**: Agent queries **local database**
  - All documents are pre-loaded in MongoDB
  - Search is just a database query (vector or text search)
  - Agent makes multiple searches, but they're all against the same local index

### Analysis

**Arguments FOR keeping search agent:**
1. **Query Refinement**: Agent can refine queries based on initial results
   - First search: "user frustration"
   - Second search: "user frustration patterns" (if first search insufficient)
   - Third search: "frustration causes" (if still insufficient)
2. **Adaptive Strategy**: Agent adapts search strategy
   - If first search returns few results → try different query
   - If results are low quality → try paraphrased query
3. **Synthesis**: Agent synthesizes results from multiple searches
   - Combines information from different search queries
   - Provides comprehensive answer

**Arguments AGAINST search agent:**
1. **Local Database**: MongoDB queries are fast and deterministic
   - No need for agent to "decide" - just query the database
   - Could use simple search function instead of agent
2. **Overhead**: Agent adds LLM overhead for simple database queries
   - Each search decision requires LLM call
   - Could be faster with direct search function
3. **Complexity**: Agent adds complexity for simple use case
   - Simple search function might be sufficient
   - Agent is overkill for local database queries

### Recommendation

**Keep the search agent, but clarify its purpose:**

1. **For Evaluation**: Keep search agent for evaluation purposes
   - Aligns with Wikipedia Agent evaluation approach
   - Allows testing agent behavior (tool calls, query refinement)
   - Enables judge evaluation and source metrics

2. **For Production**: Consider simpler approach
   - If production use case is just "search MongoDB and return results"
   - Consider direct search function instead of agent
   - Agent is useful if you need query refinement and synthesis

3. **Clarify Terminology**:
   - Rename "RAG Agent" → "Search Agent"
   - Clarify: "Search Agent that queries MongoDB with adaptive query refinement"
   - Document: Agent is useful for complex queries requiring multiple searches

## Implementation Priority

### Phase 1: Core Evaluation (High Priority)
1. ✅ Implement Judge LLM (`evals/judge.py`)
2. ✅ Implement Source Metrics (`evals/source_metrics.py`)
3. ✅ Implement Combined Score (`evals/combined_score.py`)
4. ✅ Update Ground Truth format (add `expected_sources`)
5. ✅ Create Evaluation Workflow (`evals/evaluate.py`)

### Phase 2: Testing (High Priority)
6. ✅ Update Agent Tests (`tests/search_agent/test_agent.py`)
7. ✅ Create Judge Tests (`tests/search_agent/test_judge.py`)
8. ✅ Update Tool Tests (`tests/search_agent/test_tools.py`)

### Phase 3: Refactoring (Medium Priority)
9. ✅ Rename `rag_agent/` → `search_agent/` (or keep name but clarify)
10. ✅ Remove/Deprecate `orchestrator/` module
11. ✅ Update Models (add JudgeEvaluation, JudgeResult, TokenUsage)
12. ✅ Update CLI (add `judge` and `evaluate` commands)

### Phase 4: Cleanup (Low Priority)
13. ⚠️ Remove/Deprecate `neo4j_etl/` (if not needed)
14. ⚠️ Remove/Deprecate `stream_stackexchange/` (if not needed)
15. ⚠️ Simplify `search/` module (remove chunking if not needed)

## Summary

**Key Changes Needed:**
1. Implement Judge LLM evaluation
2. Implement Source Metrics (hit rate, MRR)
3. Implement Combined Score
4. Update Ground Truth format (add expected_sources)
5. Create full evaluation workflow
6. Update tests to match Wikipedia Agent style
7. Rename/clarify "RAG Agent" → "Search Agent"
8. Remove orchestrator module (not needed for search agent evaluation)
9. Update CLI commands

**Does Search Agent Make Sense?**
- ✅ **Yes, for evaluation purposes** - Aligns with Wikipedia Agent approach
- ⚠️ **Questionable for production** - Consider simpler approach if just querying MongoDB
- ✅ **Keep it, but clarify purpose** - "Search Agent with adaptive query refinement"

**Next Steps:**
1. Start with Phase 1 (Core Evaluation)
2. Then Phase 2 (Testing)
3. Then Phase 3 (Refactoring)
4. Finally Phase 4 (Cleanup)
