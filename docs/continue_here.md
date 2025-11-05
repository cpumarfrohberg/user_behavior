# Continue Here: Model Output Extraction Debugging

## ✅ RESOLVED

**Status**: The model output capture issue has been resolved! The agent is now working correctly with OpenAI integration.

**Resolution**: After migrating from Ollama to OpenAI, the event handler is working properly and tool calls are being tracked successfully.

## Problem Statement (Historical)

**Issue**: Model output was not being captured from pydantic-ai events, making it impossible to debug validation failures.

**Symptoms** (now resolved):
- ~~Validation error: "Exceeded maximum retries (1) for output validation"~~
- ~~`_accumulated_text` is empty (no text captured)~~
- ~~No debug logs appearing from event handler~~
- Tool calls work fine (FunctionToolCallEvent is received)

## Current Status

### What's Working ✅
- Tool calls execute successfully (21+ searches completed)
- Event handler is registered and called for tool calls
- Print statements work (tool calls are displayed)
- Debug logging works in other modules (`🔍 DEBUG:` appears)
- OpenAI integration working correctly
- Agent making iterative tool calls as expected

## Resolution Summary

The issue was resolved during the migration from Ollama to OpenAI. The OpenAI integration with `pydantic-ai` works correctly with event handlers, and tool calls are now being tracked successfully.

## Key Files

- `rag_agent/agent.py` - Main agent implementation with event handler
- `rag_agent/models.py` - RAGAnswer and SearchResult models
- `rag_agent/tools.py` - Search tool functions

## Success Criteria

✅ **ALL CRITERIA MET**:
- ✅ Tool calls are being tracked and displayed correctly
- ✅ Agent is making iterative searches as expected (21+ tool calls in example run)
- ✅ Model output is captured correctly
- ✅ Event handler working properly with OpenAI integration

## Migration Notes

The issue was resolved during the migration from Ollama to OpenAI:
- Updated `rag_agent/agent.py` to use `OpenAIChatModel` with `OpenAIProvider()`
- Event handler now working correctly with OpenAI models
- Tool call tracking functioning as expected
- Model output capture working properly

## Additional Tool Ideas

### Current Tool
- `search_documents` - Search indexed MongoDB documents

### High Priority Tools to Add

1. **`filter_by_tags(tags: List[str], must_include_all: bool = False)`**
   - Filter results by specific tags (e.g., "user-behavior", "usability")
   - Useful for narrowing down by specific topics
   - Example: `filter_by_tags(["user-behavior", "e-commerce"])`

2. **`get_question_details(question_id: str)`**
   - Get full question with answers, comments, metadata
   - Provides complete context for a specific question
   - Example: `get_question_details("question_123")`

3. **`get_similar_questions(question_id: str, num_results: int = 5)`**
   - Find similar questions using StackExchange API similarity endpoint
   - Discovers related discussion threads
   - Example: `get_similar_questions("question_123", num_results=5)`

### Medium Priority Tools

4. **`filter_by_engagement(min_views: int = 0, min_votes: int = 0)`**
   - Filter by engagement metrics (views, upvotes)
   - Focus on high-quality discussions
   - Example: `filter_by_engagement(min_views=100, min_votes=5)`

5. **`get_trending_topics(tag: str = None, days: int = 7)`**
   - Get trending/hot questions in time period
   - Find current hot topics
   - Example: `get_trending_topics(tag="user-behavior", days=7)`

6. **`query_related_behaviors(behavior_keyword: str)`**
   - Query Neo4j for related behavior patterns
   - Get behavior sequences (e.g., frustration → abandonment)
   - Example: `query_related_behaviors("frustration")`

### Lower Priority Tools

7. **`filter_by_time_range(start_date: str, end_date: str)`**
   - Filter by question creation date
   - Example: `filter_by_time_range("2024-01-01", "2024-12-31")`

8. **`get_question_answers(question_id: str)`**
   - Get all answers for a specific question (sorted by votes)
   - Detailed answer analysis
   - Example: `get_question_answers("question_123")`

### Typical StackExchange API Use Cases for Agents

1. **Real-time Data Fetching**
   - When MongoDB doesn't have recent data
   - Fetching fresh questions not yet indexed
   - Getting latest discussions on trending topics

2. **Similar Question Discovery**
   - Finding related questions for context
   - Discovering discussion threads
   - Understanding question variations

3. **Engagement and Quality Metrics**
   - Getting view counts, upvotes, answer counts
   - Identifying authoritative answers
   - Filtering by community engagement

4. **User Authority Analysis**
   - Get answerer reputation scores
   - Filter by answerer expertise
   - Weight answers by user credibility

5. **Temporal Analysis**
   - Finding questions by time period
   - Identifying trending topics
   - Analyzing behavior pattern evolution

6. **Thread Exploration**
   - Getting full question-answer-comment threads
   - Understanding discussion context
   - Following comment chains

7. **Answer Quality Assessment**
   - Getting answer scores/acceptance status
   - Comparing multiple answers
   - Identifying best practices

### Example Use Case

**Question**: "What are common user frustration patterns in e-commerce?"

**Agent Workflow**:
1. `search_documents("user frustration e-commerce")` - Initial search
2. `filter_by_tags(["user-behavior", "e-commerce"])` - Refine by tags
3. `get_similar_questions(question_id)` - Find related discussions
4. `get_question_details(question_id)` - Get full context with answers
5. Synthesize comprehensive answer

### Implementation Notes

- Start with `filter_by_tags` and `get_question_details` as they complement existing search
- Use existing `StackExchangeAPIClient` for API calls
- Integrate with existing tool call tracking system
- Add to `rag_agent/tools.py`
- Update instructions to guide agent on when to use each tool

## Sentiment Analysis Ideas

### Why Sentiment Analysis Makes Sense

1. **User behavior is inherently emotional**
   - Project already focuses on frustration, satisfaction, confusion
   - Keywords include: "frustration", "satisfaction", "behavior"
   - Emotional language often signals behavior patterns

2. **Enrich behavior analysis**
   - Correlate sentiment with behaviors (negative → frustration → abandonment)
   - Identify emotional triggers (what causes negative sentiment)
   - Track sentiment evolution in discussions

3. **Enhance knowledge graph**
   - Add sentiment nodes to Neo4j: `(Question)-[:HAS_SENTIMENT]->(Sentiment)`
   - Create relationships: `(Frustration)-[:CAUSED_BY]->(NegativeSentiment)`
   - Build behavior chains: `(NegativeSentiment) → (Frustration) → (Abandonment)`

4. **Improve filtering and search**
   - Filter by sentiment: "Show me highly negative discussions about forms"
   - Weight results by sentiment intensity
   - Find emotional patterns across discussions

### Architecture: Division of Labor

#### RAG_AGENT: Lightweight Sentiment Analysis
- **Purpose**: Fast sentiment scoring for filtering/ranking search results
- **Implementation**: Use library (e.g., `textblob` or `vaderSentiment`)
- **Use Cases**:
  - Filter by sentiment: "Show me negative discussions"
  - Weight results by sentiment intensity
  - Rank results (most negative first)
  - Quick sentiment check during search

**Example**:
```python
# In RAG_AGENT tools
def search_documents(query: str, sentiment_filter: str = None):
    # ... search ...
    if sentiment_filter:
        results = filter_by_sentiment(results, sentiment_filter)
    return results
```

#### CYPHER_QUERY_AGENT: Deep Sentiment Pattern Analysis
- **Purpose**: Pattern analysis across the knowledge graph
- **Implementation**: Cypher queries on Neo4j with sentiment nodes/relationships
- **Use Cases**:
  - "What behaviors correlate with negative sentiment?"
  - "Find sentiment trends over time"
  - "Which UI patterns cause the most negative sentiment?"
  - "What's the sentiment-behavior chain: negative → frustration → abandonment?"

**Example Cypher Queries**:
```cypher
// Find behaviors with negative sentiment
MATCH (q:Question)-[:HAS_SENTIMENT]->(s:Sentiment {label: 'negative'})
MATCH (q)-[:MENTIONS]->(b:Behavior)
RETURN b.name, COUNT(*) as count
ORDER BY count DESC

// Sentiment-behavior chains
MATCH path = (s:Sentiment {label: 'negative'})-[:LEADS_TO]->(f:Frustration)-[:CAUSES]->(a:Abandonment)
RETURN path

// Sentiment trends over time
MATCH (q:Question)-[:HAS_SENTIMENT]->(s:Sentiment)
WHERE q.created_at >= date('2024-01-01')
RETURN s.label, COUNT(*) as count
ORDER BY q.created_at
```

### Benefits of This Architecture

✅ **Performance**: RAG_AGENT stays fast (library-based, no API calls)
✅ **Depth**: CYPHER_QUERY_AGENT handles complex pattern analysis
✅ **Separation of Concerns**: Each agent has clear role
✅ **Cost Efficiency**: RAG_AGENT uses free libraries, LLM only when needed

### Implementation Approach

#### 1. RAG_AGENT: Add Sentiment Field
- Add sentiment field to `SearchResult` model
- Use library (e.g., `textblob`) during indexing/search
- Add `filter_by_sentiment()` tool
- Quick sentiment scoring for search results

#### 2. Neo4j ETL: Add Sentiment Nodes
- Extract sentiment from documents during graph creation
- Create `(Question)-[:HAS_SENTIMENT]->(Sentiment)` relationships
- Store sentiment scores/intensity in Neo4j nodes
- Enable graph queries for sentiment patterns

#### 3. CYPHER_QUERY_AGENT: Update Instructions
- Add examples of sentiment-based queries
- Guide on when to query sentiment patterns
- Examples of sentiment-behavior relationship queries

### Potential Use Cases

1. **Sentiment-based filtering**
   - "What are the most frustrating user experiences?" → filter negative sentiment
   - "What design patterns lead to satisfaction?" → filter positive sentiment

2. **Sentiment trends**
   - Track sentiment over time periods
   - Identify emerging problems (increasing negative sentiment)
   - Find successful solutions (positive sentiment clusters)

3. **Behavior-sentiment correlation**
   - Map sentiment intensity to specific behaviors
   - Identify which UI elements cause strong negative reactions
   - Find what leads to positive experiences

4. **Knowledge graph enrichment**
   - Connect sentiment to behavior nodes
   - Create sentiment-behavior relationships
   - Query patterns like: "What behaviors correlate with negative sentiment?"

### Libraries to Consider

- **textblob**: Simple, free, easy to use
- **vaderSentiment**: Good for social media text, handles sarcasm
- **NLTK**: More control, requires more setup
- **spaCy**: Advanced NLP, includes sentiment analysis

**Recommendation**: Start with `textblob` or `vaderSentiment` for RAG_AGENT (fast, free, simple)

---

## Agent Evaluation Plan (Tomorrow's Task)

### Goal
Test and evaluate both RAG_AGENT and CYPHER_QUERY_AGENT (via Orchestrator) using:
1. Test functions for systematic evaluation
2. Ground truth data for validation
3. Judge LLM for automated quality assessment

### Current Evaluation Infrastructure ✅

**Existing**:
- `evals/generate_ground_truth.py` - Ground truth generation from MongoDB
- `evals/ground_truth.json` - Existing ground truth dataset
- `evals/save_results.py` - Results saving functionality
- `evals/results/` - Previous evaluation results

**What's Missing**:
- Test functions for RAG_AGENT evaluation
- Test functions for CYPHER_QUERY_AGENT evaluation
- Test functions for Orchestrator evaluation
- Judge LLM implementation
- Ground truth data for multi-agent scenarios
- Evaluation metrics and reporting

### Tasks to Complete

#### 1. Test Functions (`evals/test_agents.py`)

Create test functions for each agent:

**RAG_AGENT Tests**:
```python
async def test_rag_agent(questions: list[str], ground_truth: dict) -> dict:
    """Test RAG Agent on ground truth questions"""
    # - Initialize RAG_AGENT
    # - Run each question through agent
    # - Collect answers, tool calls, confidence scores
    # - Compare with ground truth
    # - Return metrics: accuracy, confidence, tool calls, etc.
```

**CYPHER_QUERY_AGENT Tests**:
```python
async def test_cypher_agent(questions: list[str], ground_truth: dict) -> dict:
    """Test Cypher Query Agent on ground truth questions"""
    # - Initialize CYPHER_QUERY_AGENT (once implemented)
    # - Run each question through agent
    # - Collect answers, queries executed, confidence scores
    # - Compare with ground truth
    # - Return metrics: accuracy, query quality, confidence, etc.
```

**Orchestrator Tests**:
```python
async def test_orchestrator(questions: list[str], ground_truth: dict) -> dict:
    """Test Orchestrator Agent on ground truth questions"""
    # - Initialize Orchestrator
    # - Run each question through orchestrator
    # - Track which agents were called (routing decisions)
    # - Collect synthesized answers
    # - Compare with ground truth
    # - Return metrics: routing accuracy, answer quality, agent usage, etc.
```

**Metrics to Track**:
- Answer quality (via Judge LLM)
- Routing accuracy (for orchestrator: did it choose the right agent?)
- Tool call efficiency (number of tool calls, success rate)
- Confidence scores
- Response time
- Cost (token usage)

#### 2. Ground Truth Data

**Extend Existing Ground Truth**:
- Current ground truth is focused on chunking evaluation (question → source)
- Need to extend for agent evaluation:
  - Expected answer quality
  - Expected agent routing (for orchestrator tests)
  - Expected tool usage patterns
  - Question categories (RAG vs Cypher vs Both)

**Create New Ground Truth Files**:
- `evals/ground_truth_agent_eval.json` - For agent evaluation
  ```json
  {
    "question": "What are frustrating user experiences?",
    "expected_agent": "rag_agent",  // or "cypher_query_agent" or "both"
    "expected_answer_quality": "high",
    "expected_sources": ["question_123", "question_456"],
    "category": "rag_agent"  // or "cypher_query_agent" or "both"
  }
  ```

**Question Categories**:
- **RAG_AGENT questions**: Textual content, examples, discussions
  - "What are frustrating user experiences?"
  - "How do users react to complex forms?"
  - "What are common usability problems?"
- **CYPHER_QUERY_AGENT questions**: Relationships, patterns, graph analysis
  - "What behaviors correlate with frustration?"
  - "What patterns exist in user behavior?"
  - "What leads to form abandonment?"
- **Both agents questions**: Complex multi-faceted
  - "What are frustrating experiences and what patterns do they follow?"
  - "What examples exist and how are they related?"

#### 3. Judge LLM Implementation (`evals/judge_llm.py`)

Create a **separate Judge LLM** (independent from Orchestrator) to evaluate answer quality:

**Important Distinction**:
- **Orchestrator** = One of the agents being TESTED/EVALUATED (routes questions to RAG/Cypher agents)
- **Judge LLM** = Separate evaluation component that ASSESSES answer quality (evaluates all agents including Orchestrator)

These are **independent components**:
- Orchestrator's job: Route questions and synthesize answers
- Judge LLM's job: Evaluate answer quality (separate from the agents being tested)

**JudgeScore Model** (from `neo4j_evaluation` branch - adapted for OpenAI):
```python
class JudgeScore(BaseModel):
    """Structured evaluation score from Judge LLM"""

    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score (0.0 to 1.0)")
    relevance: float = Field(..., ge=0.0, le=1.0, description="How relevant is the answer to the question?")
    completeness: float = Field(..., ge=0.0, le=1.0, description="How complete is the answer?")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="How accurate are the facts based on sources?")
    source_attribution: float = Field(..., ge=0.0, le=1.0, description="Are sources properly cited and used?")
    coherence: float = Field(..., ge=0.0, le=1.0, description="Is the answer well-structured and clear?")
    reasoning: str = Field(..., description="Brief explanation of the evaluation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Judge's confidence in this evaluation")
```

**Judge LLM Agent**:
```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

class JudgeLLM:
    """LLM-based judge for evaluating answer quality (independent evaluation component)"""

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        ground_truth: dict | None = None
    ) -> JudgeScore:
        """
        Evaluate answer quality using LLM judge.
        This is a SEPARATE component from the agents being evaluated.

        Returns:
            JudgeScore with evaluation metrics
        """
```

**Evaluation Criteria** (from `neo4j_evaluation` branch):
- **Relevance** (0.0-1.0): Does the answer directly address the question?
- **Completeness** (0.0-1.0): Is the answer thorough and comprehensive?
- **Accuracy** (0.0-1.0): Are the facts correct based on provided sources?
- **Source Attribution** (0.0-1.0): Are sources properly cited and used?
- **Coherence** (0.0-1.0): Is the answer well-structured, clear, and easy to understand?

**Note**: The `neo4j_evaluation` branch has a comprehensive Judge LLM design document (`docs/JUDGE_LLM_DESIGN.md`) with detailed implementation examples. We can adapt it for OpenAI (instead of Ollama) and use it as reference.

**Judge Instructions**:
- Use `config/instructions.py` with `InstructionType.JUDGE_AGENT` (needs to be created)
- Provide clear evaluation rubric
- Return structured scores with reasoning

**Integration**:
```python
# In test functions
judge = JudgeLLM()
for question in questions:
    answer = await agent.query(question)
    evaluation = await judge.evaluate_answer(question, answer.answer, ground_truth)
    # Collect scores...
```

#### 4. Evaluation Runner (`evals/run_evaluation.py`)

Create a main evaluation script:

```python
async def run_full_evaluation():
    """Run complete evaluation suite"""
    # 1. Load ground truth
    # 2. Test RAG_AGENT
    # 3. Test CYPHER_QUERY_AGENT (if implemented)
    # 4. Test Orchestrator
    # 5. Compare results
    # 6. Generate report
    # 7. Save results
```

**Output**:
- CSV results file
- JSON metadata file
- Summary report
- Comparison charts (if possible)

#### 5. CLI Command (`cli.py`)

Add evaluation command:

```python
@app.command()
def evaluate_agents(
    ground_truth_file: str = typer.Option(...),
    agents: str = typer.Option("rag,orchestrator", help="Comma-separated: rag,cypher,orchestrator"),
    output: str = typer.Option("evals/results/agent_evaluation.csv"),
):
    """Run evaluation suite for agents"""
    # Run evaluation...
```

### Implementation Plan

#### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   EVALUATION SYSTEM                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐      ┌──────────────┐                │
│  │ Ground Truth │      │  Judge LLM   │                │
│  │    Data      │      │  (Evaluator) │                │
│  └──────┬───────┘      └──────┬───────┘                │
│         │                      │                         │
│         ▼                      ▼                         │
│  ┌──────────────────────────────────────────┐          │
│  │         Test Functions                   │          │
│  │  (test_rag_agent, test_orchestrator)    │          │
│  └──────┬───────────────────────┬───────────┘          │
│         │                       │                      │
│         ▼                       ▼                      │
│  ┌──────────────┐      ┌──────────────┐               │
│  │  RAG_AGENT   │      │ Orchestrator │               │
│  │  (Being      │      │  (Being      │               │
│  │   Tested)    │      │   Tested)    │               │
│  └──────────────┘      └──────────────┘               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

#### Component Dependencies

```
Judge LLM (no dependencies)
    ↓
Ground Truth Data (no dependencies)
    ↓
Test Functions (depends on Judge LLM + Ground Truth)
    ↓
Evaluation Runner (depends on Test Functions)
    ↓
CLI Command (depends on Evaluation Runner)
```

#### Step-by-Step Implementation

**Phase 1: Judge LLM** (`evals/judge_llm.py`)
- **Purpose**: Independent evaluation component that assesses answer quality
- **Dependencies**: None (can be tested independently)
- **Implementation**:
  1. Create `JudgeLLM` class using `pydantic-ai`
  2. Add `JUDGE_AGENT` instruction type to `config/instructions.py`
  3. Create evaluation model (score + reasoning + criteria)
  4. Test with sample questions/answers
- **Output**: `JudgeLLM.evaluate_answer()` returns structured score

**Phase 2: Ground Truth Data** (`evals/ground_truth_agent_eval.json`)
- **Purpose**: Test dataset with expected outcomes and routing decisions
- **Dependencies**: None
- **Implementation**:
  1. Create JSON structure with questions
  2. Add fields: `question`, `expected_agent`, `category`, `expected_sources`
  3. Create 20-30 questions across categories (RAG, Cypher, Both)
  4. Optionally extend `evals/generate_ground_truth.py` to generate this
- **Output**: JSON file with test questions and expected results

**Phase 3: Test Functions** (`evals/test_agents.py`)
- **Purpose**: Run each agent on ground truth questions, collect metrics, use Judge LLM
- **Dependencies**: Judge LLM + Ground Truth
- **Implementation**:
  - `test_rag_agent()`: Initialize RAG_AGENT, run questions, collect answers/metrics, use Judge LLM
  - `test_orchestrator()`: Initialize Orchestrator, run questions, check routing accuracy, use Judge LLM
  - `test_cypher_agent()`: Placeholder for when Cypher Query Agent is implemented
- **Metrics**: Answer quality (Judge LLM), routing accuracy, tool calls, confidence, response time, token usage
- **Output**: Dictionary with results per question + aggregated metrics

**Phase 4: Evaluation Runner** (`evals/run_evaluation.py`)
- **Purpose**: Orchestrates full evaluation suite, generates reports
- **Dependencies**: Test Functions
- **Implementation**:
  1. Load ground truth
  2. Initialize Judge LLM
  3. Run test functions for each agent
  4. Compare results across agents
  5. Generate summary report
  6. Save CSV results + JSON metadata
- **Output**: CSV results file, JSON metadata, summary report (console)

**Phase 5: CLI Integration** (`cli.py`)
- **Purpose**: User-facing interface for running evaluations
- **Dependencies**: Evaluation Runner
- **Implementation**: Add `evaluate-agents` command that wraps evaluation runner
- **Usage**: `uv run ask evaluate-agents --agents "rag,orchestrator" --verbose`

#### Data Flow

```
1. Load Ground Truth
   └─> JSON file with questions + expected results

2. For each agent to test:
   ├─> Initialize agent
   ├─> For each question:
   │   ├─> Run agent.query(question)
   │   ├─> Get answer + metrics
   │   ├─> Judge LLM evaluates answer
   │   └─> Collect results
   └─> Aggregate metrics

3. Compare results across agents
   └─> Generate comparison report

4. Save results
   ├─> CSV file (detailed results)
   ├─> JSON metadata
   └─> Console summary
```

### Implementation Order

1. **Judge LLM** (`evals/judge_llm.py`) - Most critical, no dependencies
2. **Ground Truth Extension** (`evals/ground_truth_agent_eval.json`) - No dependencies
3. **Test Functions** (`evals/test_agents.py`) - Depends on Judge LLM + Ground Truth
4. **Evaluation Runner** (`evals/run_evaluation.py`) - Depends on Test Functions
5. **CLI Integration** (`cli.py`) - Depends on Evaluation Runner

### Files to Create/Modify

**New Files**:
- `evals/judge_llm.py` - Judge LLM implementation
- `evals/test_agents.py` - Test functions for agents
- `evals/run_evaluation.py` - Evaluation runner
- `evals/ground_truth_agent_eval.json` - Extended ground truth

**Modify**:
- `config/instructions.py` - Add `JUDGE_AGENT` instruction type
- `cli.py` - Add `evaluate-agents` command
- `evals/generate_ground_truth.py` - Extend for agent evaluation ground truth (optional)

### Success Criteria

- ✅ Judge LLM can evaluate answer quality consistently
- ✅ Test functions can run both agents systematically
- ✅ Ground truth data covers RAG, Cypher, and Both scenarios
- ✅ Evaluation runner generates comprehensive reports
- ✅ Results can be compared across agents
- ✅ Routing accuracy measured for orchestrator
- ✅ CLI command works end-to-end

### Notes

- Judge LLM should use a consistent model (e.g., `gpt-4o-mini` for cost efficiency)
- Evaluation should be deterministic (same questions → same results)
- Results should be saved for comparison over time
- Consider using `pydantic-ai` for Judge LLM (consistent with other agents)
- Test functions should be async (agents are async)
- Consider adding progress indicators for long-running evaluations
