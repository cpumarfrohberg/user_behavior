# Search Agent Architecture Analysis: MongoDB vs SQL vs StackExchange API

## Context: Bank Client Satisfaction Analysis System

**Project Goal**: Implement a client satisfaction analysis system for a bank

**Key Requirements**:
- **Security**: Local database (MongoDB) for information security reasons
- **Architecture**: Orchestrator + 2 agents:
  - **Search Agent**: API calls + MongoDB queries (document retrieval)
  - **Cypher Agent**: Neo4j relationship queries (client relationship analysis)
- **Performance Issue**: Ollama was slow, possibly due to loading all documents from MongoDB
- **Data Flow**: External API → Save to local MongoDB → Query MongoDB
- **Use Case**: Bank client satisfaction analysis (sensitive data, security-critical)

**Security Constraints**:
- ❌ Cannot use external APIs for production data (security requirement)
- ✅ Must use local MongoDB for production
- ✅ Local models preferred (Ollama) but performance is a concern

---

## Current Implementation: How Search Agent Extracts Content from MongoDB

### Architecture Flow

```
┌─────────────────┐
│   MongoDB       │
│  (questions)    │
└────────┬────────┘
         │
         │ 1. Load ALL documents at initialization
         │    collection.find({}, {"_id": 0})
         │
         ▼
┌─────────────────┐
│  RAGAgent       │
│  initialize()   │
└────────┬────────┘
         │
         │ 2. Parse documents
         │    - Combine title + body → content
         │    - Create source: "question_{question_id}"
         │
         ▼
┌─────────────────┐
│  Chunking       │
│  (optional)     │
└────────┬────────┘
         │
         │ 3. Split documents into chunks
         │    - chunk_size: 500 chars (default)
         │    - chunk_overlap: 0 (default)
         │
         ▼
┌─────────────────┐
│  Search Index   │
│  (in-memory)    │
└────────┬────────┘
         │
         │ 4. Add chunks to search index
         │    - MinSearch: text-based search
         │    - SentenceTransformers: vector embeddings
         │
         ▼
┌─────────────────┐
│  Agent Query    │
│  (runtime)       │
└────────┬────────┘
         │
         │ 5. Agent searches in-memory index
         │    - NOT querying MongoDB directly
         │    - Multiple searches with different queries
         │
         ▼
┌─────────────────┐
│  Search Results  │
│  (from index)     │
└─────────────────┘
```

### Key Code Flow

**1. Initialization (Load from MongoDB):**
```python
# rag_agent/agent.py:134-161
def _load_from_mongodb(self, should_chunk: bool = True) -> None:
    # Connect to MongoDB
    client = MongoClient(self.config.mongo_uri)
    db = client[self.config.database]
    collection_obj = db[self.config.collection]

    # Load ALL documents (no filtering)
    docs = list(collection_obj.find({}, {"_id": 0}))

    # Parse: combine title + body
    documents = self._parse_mongodb_documents(docs)

    # Chunk documents (split into smaller pieces)
    chunked_docs = chunk_documents(documents, chunk_size, overlap)

    # Add to in-memory search index
    self.search_index.add_documents(chunked_docs)
```

**2. Runtime Search (In-Memory Index):**
```python
# rag_agent/tools.py:40-94
def search_documents(query: str, num_results: int = 2) -> List[SearchResult]:
    # Search in-memory index (NOT MongoDB)
    results = _search_index.search(query=query, num_results=num_results)

    # Returns results from index, not from MongoDB
    return search_results
```

### Important Characteristics

1. **Pre-loading**: All documents are loaded from MongoDB at initialization
2. **In-Memory Index**: Search happens against in-memory index, not MongoDB
3. **Chunking**: Documents are split into chunks for better retrieval
4. **Vector/Text Search**: Uses either MinSearch (text) or SentenceTransformers (vector)
5. **No Real-Time Updates**: Index is static until re-initialization

## Comparison: Current vs SQL vs StackExchange API

### Option 1: Current Approach (In-Memory Index)

**How it works:**
- Load all documents from MongoDB → Chunk → Create in-memory index
- Agent searches in-memory index (vector or text search)
- Agent can make multiple searches with different queries

**Pros:**
- ✅ Fast search (in-memory, no database queries)
- ✅ Semantic search (vector embeddings)
- ✅ Agent can refine queries based on results
- ✅ No API rate limits
- ✅ Works offline

**Cons:**
- ❌ Memory intensive (all documents loaded)
- ❌ Limited to 500 documents (hardcoded limit)
- ❌ No real-time updates (must re-initialize)
- ❌ Not using MongoDB's native search capabilities
- ❌ Chunking may split context

**Use Case:**
- Good for: Static dataset, semantic search, offline use
- Bad for: Large datasets, real-time updates, structured queries

---

### Option 2: SQL Queries (MongoDB Native Queries)

**How it would work:**
- Agent translates user question → MongoDB query
- Direct queries to MongoDB (no pre-loading)
- Use MongoDB's text search or aggregation pipeline

**Example:**
```python
# Agent generates MongoDB query
query = {
    "$text": {"$search": "user frustration patterns"},
    "tags": {"$in": ["user-behavior", "usability"]}
}
results = collection.find(query)
```

**Pros:**
- ✅ Real-time data (always current)
- ✅ No memory limits (query only what you need)
- ✅ Use MongoDB's native text search
- ✅ Can use aggregation pipelines for complex queries
- ✅ Efficient for large datasets
- ✅ Can filter by tags, dates, scores, etc.

**Cons:**
- ❌ No semantic search (unless using MongoDB Atlas Vector Search)
- ❌ Agent needs to generate structured queries
- ❌ Less flexible than vector search
- ❌ Requires MongoDB query knowledge

**Use Case:**
- Good for: Large datasets, real-time data, structured queries, filtering
- Bad for: Semantic search, similarity matching

---

### Option 3: StackExchange API Calls

**How it would work:**
- Agent calls StackExchange API directly
- Similar to Wikipedia Agent pattern
- Agent coordinates multiple API calls

**Example:**
```python
# Agent makes API calls
def stackexchange_search(query: str) -> List[SearchResult]:
    # Call StackExchange API
    response = requests.get(
        "https://api.stackexchange.com/2.3/search",
        params={"q": query, "site": "ux", ...}
    )
    return parse_results(response.json())

def stackexchange_get_question(question_id: int) -> Question:
    # Get full question details
    response = requests.get(
        f"https://api.stackexchange.com/2.3/questions/{question_id}",
        params={"site": "ux", "filter": "withbody", ...}
    )
    return parse_question(response.json())
```

**Pros:**
- ✅ Always up-to-date (live data)
- ✅ No local storage needed
- ✅ Matches Wikipedia Agent pattern (for evaluation)
- ✅ Agent orchestrates external API calls (makes sense)
- ✅ Can search across all StackExchange sites

**Cons:**
- ❌ API rate limits (300 requests/day without key, 10,000 with key)
- ❌ Network latency (slower than local)
- ❌ Requires internet connection
- ❌ Limited query options (StackExchange API constraints)
- ❌ No semantic search (API only supports text search)

**Use Case:**
- Good for: Live data, evaluation (matches Wikipedia Agent), no local storage
- Bad for: Offline use, high-volume queries, semantic search

---

## Recommendation: Which Approach Makes Sense?

### For Production (Bank Client Satisfaction Analysis)

**✅ Use MongoDB Native Queries (REQUIRED for Security)**

**Reasoning:**
1. **Security Requirement**: Bank data must stay local (cannot use external APIs)
2. **Real-Time Data**: Always current, no stale data
3. **Scalability**: Can handle large datasets efficiently
4. **Performance**: Query only what you need (fixes Ollama slowness issue)
5. **Architecture Fit**: Works with orchestrator pattern (Search Agent + Cypher Agent)

**Implementation:**
```python
# Agent generates MongoDB queries (no pre-loading)
def search_mongodb(query: str, filters: dict = None) -> List[SearchResult]:
    # Query MongoDB directly (not pre-loaded index)
    pipeline = [
        {"$match": {"$text": {"$search": query}}},
        {"$limit": num_results}
    ]
    results = collection.aggregate(pipeline)
    return parse_results(results)
```

**Performance Optimization (Fixes Ollama Slowness):**
```python
# DON'T load all documents at initialization
# Instead, query MongoDB on-demand
class SearchAgent:
    def __init__(self, config):
        self.config = config
        self.client = MongoClient(config.mongo_uri)
        self.collection = self.client[config.database][config.collection]
        # NO pre-loading - query on-demand

    def search(self, query: str, num_results: int = 5):
        # Query MongoDB directly (fast, no memory overhead)
        results = self.collection.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(num_results)
        return list(results)
```

**Why This Fixes Ollama Performance:**
- ❌ **Current**: Loads ALL documents → Creates embeddings → Stores in memory → Slow initialization
- ✅ **Optimized**: Queries MongoDB on-demand → Only processes relevant documents → Fast

---

### For Evaluation (Aligning with Wikipedia Agent)

**✅ Use StackExchange API Calls (Public Data Only)**

**Reasoning:**
1. **Matches Wikipedia Agent Pattern**: Wikipedia Agent calls external API → StackExchange Agent should call external API
2. **Agent Orchestration Makes Sense**: Agent coordinating multiple API calls is a valid use case
3. **Evaluation Consistency**: Same pattern for evaluation (external API → agent → judge)
4. **No Local Data Dependency**: Don't need MongoDB populated for evaluation
5. **Public Data**: StackExchange is public data, safe for evaluation

**Implementation:**
```python
# Similar to Wikipedia Agent
tools = [
    stackexchange_search,      # Search StackExchange
    stackexchange_get_question, # Get full question details
]
```

**Note**: This is ONLY for evaluation with public data. Production MUST use local MongoDB.

---

### Current Approach (In-Memory Index) - Performance Issue Identified

**Problem with Current Approach:**
- ❌ **Pre-loads ALL documents** at initialization → Memory intensive
- ❌ **Creates embeddings for all documents** → Slow initialization
- ❌ **Hardcoded limit of 500 documents** → Doesn't scale
- ❌ **Ollama slowness**: Likely caused by loading all documents into memory

**Why Ollama Was Slow:**
1. Loading all documents from MongoDB → Memory overhead
2. Creating embeddings for all documents → CPU intensive
3. Storing all embeddings in memory → Memory pressure
4. Ollama processes all this data → Slow response

**Solution:**
- ✅ **Query MongoDB on-demand** → Only process relevant documents
- ✅ **No pre-loading** → Fast initialization
- ✅ **No memory overhead** → Scales to any dataset size
- ✅ **Faster Ollama** → Only processes query results, not all documents

**When to Keep Current Approach:**
- ⚠️ Only if you need offline capability AND dataset is small (< 500 documents)
- ⚠️ But still consider on-demand queries for better performance

**When to Replace:**
- ✅ **Production (REQUIRED)**: Must use MongoDB native queries for security
- ✅ **Large datasets**: On-demand queries scale better
- ✅ **Performance**: Fixes Ollama slowness
- ✅ **Real-time data**: Always current, no stale data

---

## Recommended Architecture for Bank Client Satisfaction Analysis

### Production Architecture (Security-Compliant)

```
┌─────────────────┐
│   External API  │
│  (Client Data)  │
└────────┬────────┘
         │
         │ 1. Fetch client discussions
         │
         ▼
┌─────────────────┐
│   MongoDB       │
│  (Local DB)     │ ← Security: Local storage
└────────┬────────┘
         │
         │ 2. Query on-demand (no pre-loading)
         │
         ▼
┌─────────────────┐
│  Orchestrator   │
│     Agent       │
└────────┬────────┘
         │
         ├───→ Search Agent (MongoDB queries)
         │     - Document retrieval
         │     - On-demand queries (fast)
         │
         └───→ Cypher Agent (Neo4j queries)
               - Client relationships
               - Pattern analysis
```

### Search Agent Implementation (Production)

**Key Changes:**
1. **No Pre-loading**: Query MongoDB on-demand
2. **MongoDB Native Queries**: Use text search or aggregation
3. **Performance**: Only process relevant documents
4. **Security**: All data stays local

**Implementation:**
```python
class SearchAgent:
    """Search Agent for bank client satisfaction analysis"""

    def __init__(self, config):
        self.config = config
        # Connect to MongoDB (no pre-loading)
        self.client = MongoClient(config.mongo_uri)
        self.collection = self.client[config.database][config.collection]
        # NO search index initialization

    def search_documents(self, query: str, num_results: int = 5):
        """Query MongoDB on-demand (fast, no memory overhead)"""
        # Use MongoDB text search
        results = self.collection.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(num_results)

        return list(results)

    # Optional: For semantic search, use MongoDB Atlas Vector Search
    def search_vector(self, query_embedding, num_results: int = 5):
        """Use MongoDB Atlas Vector Search (if available)"""
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 100,
                    "limit": num_results
                }
            }
        ]
        return list(self.collection.aggregate(pipeline))
```

### Evaluation Architecture (Public Data Only)

**For evaluation/testing with public data:**
- Use StackExchange API calls (matches Wikipedia Agent pattern)
- Agent orchestrates API calls
- Judge evaluates results

**Implementation:**
```python
class SearchAgent:
    def __init__(self, mode: str = "production"):
        self.mode = mode
        if mode == "evaluation":
            # Use StackExchange API (public data)
            self.tools = [stackexchange_search, stackexchange_get_question]
        else:
            # Use MongoDB queries (production, secure)
            self.tools = [mongodb_search, mongodb_get_question]
```

### Orchestrator Integration

**The orchestrator routes to:**
1. **Search Agent**: For document retrieval (MongoDB queries)
2. **Cypher Agent**: For relationship analysis (Neo4j queries)

**This architecture makes sense because:**
- ✅ Search Agent handles document retrieval (MongoDB)
- ✅ Cypher Agent handles relationship analysis (Neo4j)
- ✅ Orchestrator intelligently routes based on question type
- ✅ Both agents query local databases (security compliant)

---

## Summary

### Current Implementation (Identified Issues)
- **What**: Pre-loads all documents from MongoDB → Creates in-memory index → Searches index
- **Issues**:
  - ❌ Memory-intensive (loads all documents)
  - ❌ Slow initialization (creates embeddings for all documents)
  - ❌ **Ollama slowness**: Likely caused by loading all documents into memory
  - ❌ Limited to 500 documents (hardcoded)
  - ❌ Not using MongoDB's native capabilities
  - ❌ Not aligned with Wikipedia Agent pattern for evaluation

### Recommended for Production (Bank Client Satisfaction)
- **✅ MongoDB Native Queries (ON-DEMAND)**:
  - Security: All data stays local (required for bank)
  - Performance: Fixes Ollama slowness (no pre-loading)
  - Scalability: Handles large datasets efficiently
  - Real-time: Always current data
  - Architecture: Works with orchestrator (Search Agent + Cypher Agent)

### Recommended for Evaluation (Public Data Only)
- **✅ StackExchange API Calls**:
  - Matches Wikipedia Agent pattern
  - Agent orchestrates external API calls
  - No local data dependency
  - Safe for evaluation (public data)

### Decision Matrix (Updated for Bank Context)

| Approach | Evaluation | Production | Security | Performance | Scalability |
|----------|-----------|------------|----------|------------|-------------|
| **In-Memory Index** (Current) | ⚠️ Works but not aligned | ❌ **Not secure** | ❌ External data | ❌ **Slow (Ollama)** | ❌ Limited (500 docs) |
| **MongoDB Queries (On-Demand)** | ⚠️ Works but different pattern | ✅ **Yes (secure)** | ✅ Local DB | ✅ **Fast (fixes Ollama)** | ✅ **Unlimited** |
| **StackExchange API** | ✅ **Best (aligned)** | ❌ **Not secure** | ❌ External API | ✅ Fast | ⚠️ API limits |

### Performance Optimization: Fixing Ollama Slowness

**Root Cause:**
- Pre-loading all documents → Memory overhead
- Creating embeddings for all documents → CPU intensive
- Ollama processes all this data → Slow response

**Solution:**
- ✅ Query MongoDB on-demand → Only process relevant documents
- ✅ No pre-loading → Fast initialization
- ✅ No memory overhead → Scales to any dataset size
- ✅ Faster Ollama → Only processes query results

---

## Next Steps

### Immediate Actions

1. **For Production (REQUIRED)**:
   - ✅ Refactor Search Agent to query MongoDB on-demand (no pre-loading)
   - ✅ Use MongoDB native text search or aggregation pipelines
   - ✅ Optional: MongoDB Atlas Vector Search for semantic search
   - ✅ Test with Ollama to verify performance improvement

2. **For Evaluation (Optional)**:
   - ✅ Implement StackExchange API calls (like Wikipedia Agent)
   - ✅ Use for evaluation/testing with public data only
   - ✅ Keep separate from production code

3. **Architecture**:
   - ✅ Keep Orchestrator (routes to Search Agent + Cypher Agent)
   - ✅ Search Agent: MongoDB queries (document retrieval)
   - ✅ Cypher Agent: Neo4j queries (relationship analysis)

### Implementation Priority

1. **High Priority**: Refactor Search Agent to use on-demand MongoDB queries (fixes Ollama slowness)
2. **Medium Priority**: Implement StackExchange API for evaluation (aligns with Wikipedia Agent)
3. **Low Priority**: Optimize MongoDB queries with indexes and aggregation pipelines
