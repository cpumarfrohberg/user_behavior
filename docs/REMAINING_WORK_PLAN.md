# Remaining Work Plan

## Overview

This document outlines the remaining work items for the user behavior RAG system, focusing on evaluation, optimization, and potential features.

---

## Completed ✅

### 1. Chunking Evaluation System
- ✅ Evaluation metrics (hit_rate, MRR, token counting, scoring)
- ✅ Grid search for parameter optimization
- ✅ CLI commands (`generate-ground-truth`, `evaluate-chunking`)
- ✅ Ground truth generation from MongoDB
- ✅ All constants moved to config (no hard-coded values)
- ✅ Type safety with enums (TokenizerModel, TokenizerEncoding)
- ✅ Code organization (instructions separated)

### 2. Configuration
- ✅ Default search type: SentenceTransformers (vector search)
- ✅ Instructions separated into `config/instructions.py`
- ✅ Import order fixed (E402 resolved)

### 3. Documentation
- ✅ README updated with evaluation workflow
- ✅ All CLI commands documented

---

## Remaining Work

### Priority 1: Optional Cleanup

#### 1.1 Remove MinSearch Support (Optional)
**Status**: MinSearch still exists in codebase
**Decision Needed**: Keep as fallback or remove entirely

**If removing**:
- Remove `MINSEARCH` from `SearchType` enum
- Remove MinSearch implementation from `search/flexible_search.py`
- Remove `--search-type` option from CLI
- Update `search/search_utils.py` to only support SentenceTransformers
- Remove MinSearch mentions from README
- Remove `minsearch` dependency from `pyproject.toml`

**Effort**: ~2 hours
**Risk**: Low (if SentenceTransformers is reliable)

---

### Priority 2: Answer Quality Evaluation

#### 2.1 Judge LLM Implementation
**Status**: Configuration exists, implementation missing
**Priority**: Medium (after chunking eval is optimized)

**What's needed**:
1. Create `JudgeLLM` class or extend `OllamaLLM`
   - Use `DEFAULT_JUDGE_MODEL` (phi3:mini)
   - Use `DEFAULT_JUDGE_TEMPERATURE` (0.1 for consistency)

2. Implement answer evaluation function
   ```python
   def evaluate_answer_quality(
       question: str,
       answer: str,
       context: list[dict],
       judge_llm: JudgeLLM,
   ) -> float:
       """Evaluate answer quality. Returns 0.0-1.0 score."""
   ```

3. Integration options:
   - **Option A**: Separate module (`evals/judge_evaluation.py`)
   - **Option B**: Add to `search/simple_chunking.py`
   - **Option C**: Add to `source/text_rag.py` as method

4. CLI command (optional):
   - `evaluate-answers` command to evaluate RAG outputs
   - Or integrate into existing evaluation pipeline

**Design decisions**:
- Binary evaluation (relevant/not relevant) or continuous score (0.0-1.0)?
- Evaluate individual answers or batch evaluation?
- Separate from chunking eval or combined pipeline?

**Effort**: ~4-6 hours
**Risk**: Medium (LLM-based evaluation can be inconsistent)

**Best practices to consider**:
- Structured output (JSON) for reliability
- Prompt engineering for consistency
- Caching judge responses if re-running
- Human-in-the-loop validation

---

### Priority 3: System Integration

#### 3.1 Cypher Query Agent
**Status**: Instructions exist, implementation missing
**Priority**: Low (separate from RAG evaluation)

**What's needed**:
- Neo4j connection and query execution
- Natural language to Cypher conversion
- Graph query result interpretation
- Integration with orchestrator agent

**Note**: This is separate from chunking evaluation work.

---

#### 3.2 Orchestrator Agent
**Status**: Instructions exist, implementation missing
**Priority**: Low

**What's needed**:
- Conversation history management
- Query routing (RAG vs Cypher)
- Response synthesis from multiple agents
- Error handling and fallback strategies

---

### Priority 4: Testing & Validation

#### 4.1 Test the Evaluation Pipeline
**Status**: Not tested end-to-end
**Priority**: Medium

**What's needed**:
1. Run ground truth generation
2. Run chunking evaluation
3. Verify results make sense
4. Test edge cases (empty ground truth, no documents, etc.)

**Effort**: ~2-3 hours

---

#### 4.2 Add Unit Tests
**Status**: No tests for evaluation functions
**Priority**: Low-Medium

**What's needed**:
- Unit tests for `_hit_rate()`, `_mrr()`, `_calculate_score()`
- Mock tests for `evaluate_chunking_params()`
- Integration tests for grid search

**Effort**: ~4-6 hours

---

### Priority 5: Optimization & Enhancement

#### 5.1 CLI Default Mismatch
**Status**: CLI defaults to `"minsearch"`, config defaults to `SentenceTransformers`
**Priority**: Medium

**What's needed**:
- Update CLI `ask` command to use `DEFAULT_SEARCH_TYPE` from config
- Remove hard-coded `"minsearch"` default

**Effort**: ~15 minutes

---

#### 5.2 Hybrid Search (Future)
**Status**: Not implemented
**Priority**: Low (future enhancement)

**What's needed**:
- Combine vector search + text search scores
- Weighted combination: `score = alpha * vector_score + beta * text_score`
- Requires both search methods working

**Effort**: ~6-8 hours (if both search types available)

---

#### 5.3 Evaluation Caching
**Status**: Not implemented
**Priority**: Low

**What's needed**:
- Cache search results per query to avoid recomputation
- Cache judge evaluations if re-running
- Useful for iterative evaluation development

**Effort**: ~3-4 hours

---

## Recommended Order

### Phase 1: Cleanup & Validation (1-2 days)
1. ✅ Test evaluation pipeline end-to-end
2. Fix CLI default mismatch
3. **Decision**: Remove MinSearch or keep it?

### Phase 2: Answer Quality Evaluation (2-3 days)
1. Implement Judge LLM (if needed)
2. Create answer evaluation pipeline
3. Test judge consistency

### Phase 3: Testing & Polish (1-2 days)
1. Add unit tests
2. Integration tests
3. Documentation polish

---

## Blocked / Depends On

- **Judge LLM**: Depends on chunking eval being optimized first
- **Cypher Agent**: Requires Neo4j setup and data
- **Orchestrator**: Requires both RAG and Cypher agents working

---

## Decisions Needed

1. **MinSearch**: Remove entirely or keep as fallback?
2. **Judge LLM**: Binary (yes/no) or continuous score (0.0-1.0)?
3. **Evaluation Location**: Separate module or integrate into existing code?
4. **Testing Priority**: Unit tests first or test pipeline first?

---

## Notes

- Chunking evaluation is **production-ready** ✅
- Judge LLM is **nice-to-have** for complete evaluation
- Current focus should be on **optimizing retrieval** (chunking eval) first
- Judge LLM can wait until retrieval is optimized

---

## Summary

**Immediate (before next milestone)**:
- Test evaluation pipeline
- Fix CLI default mismatch

**Short-term (next 1-2 weeks)**:
- Judge LLM implementation (if needed)
- Basic testing

**Long-term (future)**:
- Cypher agent implementation
- Orchestrator agent
- Hybrid search
- Comprehensive test suite
