# Neo4j ETL Implementation Plan

## Overview
Refactor `neo4j_etl/src/dump_stackexchange_payload.py` to load StackExchange data from MongoDB into Neo4j as a knowledge graph.

---

## Architecture Decisions

### Data Source
- **Source**: MongoDB collection (`MONGO_COLLECTION_NAME` or `questions`)
- **Format**: Pydantic models (already structured via `stream_stackexchange/setup_data_pipeline.py`)
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
- MongoDB: Uses existing `MONGO_URI`, `MONGO_DB_NAME`, `MONGO_COLLECTION_NAME`

---

## Implementation Structure

### Main Function
```python
@retry(tries=100, delay=10)
def load_stackexchange_graph_from_mongodb() -> None:
    """
    1. Connect to MongoDB and Neo4j
    2. Read all documents from MongoDB collection
    3. Create constraints
    4. Create nodes (Users, Tags, Questions, Answers, Comments)
    5. Create relationships
    6. Log progress
    """
```

### Helper Functions

1. **`_set_uniqueness_constraints(tx, node_label)`**
   - Creates constraints for all node types
   - Called for: User, Question, Answer, Comment, Tag

2. **Node Creation Functions** (use parameterized Cypher MERGE):
   - `_create_users()` - Batch MERGE User nodes
   - `_create_tags()` - Batch MERGE Tag nodes
   - `_create_questions()` - Batch MERGE Question nodes
   - `_create_answers()` - Batch MERGE Answer nodes
   - `_create_comments()` - Batch MERGE Comment nodes

3. **Relationship Creation Functions** (use parameterized Cypher):
   - `_create_user_question_relationships()` - ASKED
   - `_create_user_answer_relationships()` - ANSWERED
   - `_create_user_comment_relationships()` - COMMENTED
   - `_create_question_answer_relationships()` - HAS_ANSWER
   - `_create_question_comment_relationships()` - HAS_COMMENT (question comments)
   - `_create_answer_comment_relationships()` - HAS_COMMENT (answer comments)
   - `_create_question_tag_relationships()` - HAS_TAG
   - `_create_accepted_answer_relationships()` - ACCEPTED ⭐

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

### Imports Needed:
```python
import logging
import os
from typing import Any

from neo4j import GraphDatabase
from pymongo import MongoClient
from retry import retry

from config import (
    MONGODB_URI, MONGODB_DB, MONGODB_COLLECTION,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
)
```

### Already Available:
- `neo4j` package (in pyproject.toml: `neo4j==5.14.1`)
- `retry` package (in pyproject.toml: `retry==0.9.2`)
- `pymongo` package (already used in collector)

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

Follow the structure of `hospital_bulk_csv_write.py`:
- Similar logging approach
- Similar constraint creation pattern
- Similar batch transaction pattern
- Replace `LOAD CSV` with parameterized `MERGE` statements

---

## Next Steps

1. Add Neo4j config constants to `config/__init__.py`
2. Create `dump_stackexchange_payload.py` with full implementation
3. Test with small dataset
4. Run full ETL on complete MongoDB collection
5. Verify graph structure in Neo4j Browser
