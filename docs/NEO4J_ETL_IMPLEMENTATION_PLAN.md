# Neo4j ETL Implementation Plan

## Overview
ETL pipeline to load StackExchange data from MongoDB into Neo4j as a knowledge graph. The implementation is organized into modular components: `extract.py` (data transformation), `validate.py` (Neo4j-specific validation), and `inject.py` (Neo4j operations), orchestrated by `dump_stackexchange_payload.py`.

---

## Architecture Decisions

### Data Source
- **Source**: MongoDB collection (`MONGO_COLLECTION_NAME` or `questions`)
- **Format**: Pydantic models (already structured via `stream_stackexchange/collector.py`)
- **Structure**: `Question` objects containing `User`, `Answer`, `Comment`, and `Tag` data

### Data Destination
- **Database**: Neo4j
- **Method**: Direct Cypher MERGE statements with parameters (no CSV intermediate files)
- **Approach**: Batch processing (50-100 questions per transaction)

---

## Graph Model

### Nodes

1. **User**
   - Properties: `user_id` (unique), `display_name`, `reputation`
   - Constraint: `user_id IS UNIQUE`

2. **Question**
   - Properties: `question_id` (unique), `title`, `body` (truncated to 500 chars), `score`, `site`, `collected_at`
   - Constraint: `question_id IS UNIQUE`

3. **Answer**
   - Properties: `answer_id` (unique), `body` (truncated to 500 chars), `score`, `is_accepted`
   - Constraint: `answer_id IS UNIQUE`

4. **Comment**
   - Properties: `comment_id` (unique), `body` (truncated to 200 chars), `score`
   - Constraint: `comment_id IS UNIQUE`

5. **Tag**
   - Properties: `name` (unique)
   - Constraint: `name IS UNIQUE`

### Relationships

1. `User -[:ASKED]-> Question`
2. `User -[:ANSWERED]-> Answer`
3. `User -[:COMMENTED]-> Comment`
4. `Question -[:HAS_ANSWER]-> Answer`
5. `Question -[:HAS_COMMENT]-> Comment` (for comments on questions)
6. `Answer -[:HAS_COMMENT]-> Comment` (for comments on answers)
7. `Question -[:HAS_TAG]-> Tag`
8. `Question -[:ACCEPTED]-> Answer` (when `is_accepted=True`) ⭐

---

## Configuration

### Add to `config/__init__.py`:
```python
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_secure_password")
```

### Environment Variables:
- `NEO4J_URI` (default: `bolt://localhost:7687`)
- `NEO4J_USER` (default: `neo4j`)
- `NEO4J_PASSWORD` (required)
- MongoDB: Uses `MONGO_URI`, `MONGO_DB_NAME`, `MONGO_COLLECTION_NAME` which map to config constants `MONGODB_URI`, `MONGODB_DB`, `MONGODB_COLLECTION`

---

## Implementation Structure

### Module Organization

The ETL is organized into three modules:

1. **`extract.py`** - Data collection and transformation
   - `collect_batch_data()` - Transforms MongoDB documents into Neo4j-ready batch data
   - `_add_user_if_new()` - Helper for user deduplication

2. **`validate.py`** - Neo4j-specific validation (Option B: trust MongoDB, validate Neo4j-specifics)
   - `validate_user()` - Validates and normalizes user data
   - `validate_question()` - Validates question with body truncation (500 chars)
   - `validate_answer()` - Validates answer with body truncation (500 chars)
   - `validate_comment()` - Validates comment with body truncation (200 chars)
   - `validate_tag()` - Validates tag names
   - `_validate_post_with_body()` - DRY helper for post validation

3. **`inject.py`** - Neo4j operations
   - `set_uniqueness_constraints()` - Creates uniqueness constraints for all node types
   - `_create_nodes()` - Batch creates all node types (Users, Tags, Questions, Answers, Comments)
   - `_create_relationships()` - Batch creates all relationships
   - `process_batch()` - Orchestrates node and relationship creation in a single transaction

4. **`dump_stackexchange_payload.py`** - Main orchestrator
   - `load_stackexchange_graph_from_mongodb()` - Main function that coordinates the ETL pipeline

### Main Function
```python
@retry(tries=100, delay=10)
def load_stackexchange_graph_from_mongodb() -> None:
    """
    1. Connect to MongoDB and Neo4j
    2. Read all documents from MongoDB collection
    3. Create constraints (via inject.py)
    4. Process batches: extract → validate → inject
    5. Log progress
    """
```

---

## Key Implementation Details

### Text Truncation
- **Questions/Answers**: First 500 characters of `body`
- **Comments**: First 200 characters of `body`
- **Rationale**: Full text stored in MongoDB; Neo4j focuses on graph structure and relationships

### Batch Processing
- Process **50-100 questions per transaction** for optimal performance
- Use `session.execute_write()` for batched operations
- Log progress after each batch

### Handling Null/Empty Data
- **Missing owners**: Skip relationship creation (node may exist from other context)
- **Empty lists**: Check before iterating (tags, answers, comments)
- **Null values**: Use `IS NOT NULL` checks in Cypher where appropriate

### Parameterized Queries
- Use Cypher parameters, not string interpolation
- Example:
  ```cypher
  MERGE (u:User {user_id: $user_id})
  SET u.display_name = $display_name, u.reputation = $reputation
  ```
  Not:
  ```cypher
  MERGE (u:User {user_id: {user_id}})
  ```

---

## Execution Order

1. **Setup**: Connect to MongoDB and Neo4j
2. **Constraints**: Create all uniqueness constraints
3. **Nodes** (in dependency order):
   - Users (no dependencies)
   - Tags (no dependencies)
   - Questions (depends on Users)
   - Answers (depends on Users)
   - Comments (depends on Users)
4. **Relationships** (after all nodes exist):
   - User relationships (ASKED, ANSWERED, COMMENTED)
   - Question relationships (HAS_ANSWER, HAS_COMMENT, HAS_TAG)
   - Answer relationships (HAS_COMMENT)
   - Accepted relationships (ACCEPTED)

---

## Dependencies

### Key Imports:
```python
# dump_stackexchange_payload.py
from neo4j import GraphDatabase
from pymongo import MongoClient
from retry import retry

from config import (
    MONGODB_URI, MONGODB_DB, MONGODB_COLLECTION,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
)

# extract.py
from neo4j_etl.src.validate import (
    validate_answer, validate_comment, validate_question,
    validate_tag, validate_user
)

# inject.py
# Uses neo4j transaction functions (tx parameter)
```

### Packages:
- `neo4j==5.14.1` - Neo4j Python driver
- `retry==0.9.2` - Retry decorator for resilient operations
- `pymongo` - MongoDB Python driver (already used in collector)

---

## Error Handling

- Use `@retry` decorator on main function (like hospital example)
- Log errors but continue processing (don't fail entire batch)
- Handle missing/None owners gracefully
- Validate data before creating nodes/relationships

---

## Testing Checklist

- [ ] Test with small dataset (5-10 questions)
- [ ] Verify all node types created correctly
- [ ] Verify all relationships created correctly
- [ ] Check uniqueness constraints work (duplicate prevention)
- [ ] Verify text truncation applied
- [ ] Test ACCEPTED relationship creation
- [ ] Test with missing/null data (owners, comments, tags)
- [ ] Verify batch processing works correctly
- [ ] Test full dataset integration

---

## Reference Pattern

Follow the structure of similar ETL patterns:
- Similar logging approach
- Similar constraint creation pattern
- Similar batch transaction pattern
- Use parameterized `MERGE` statements (not CSV loading)

---

## Implementation Status

### ✅ Completed
1. ✅ Neo4j config constants added to `config/__init__.py`
2. ✅ Modular architecture implemented (`extract.py`, `validate.py`, `inject.py`)
3. ✅ `dump_stackexchange_payload.py` orchestrator created
4. ✅ Comprehensive test suite written (`test_extract.py`, `test_validate.py`, `test_inject.py`)

### Next Steps

1. Run ETL with small test dataset (5-10 questions)
2. Verify graph structure in Neo4j Browser
3. Run full ETL on complete MongoDB collection
4. Monitor performance and optimize batch size if needed
