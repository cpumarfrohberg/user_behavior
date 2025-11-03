# Chunking Parameter Evaluation Integration Plan

## Overview
Add parameter evaluation functions to `search/simple_chunking.py` to systematically test chunk_size and overlap combinations with ground truth data.

---

## What Would Be Added to `simple_chunking.py`

### 1. **Evaluation Metrics Functions**

```python
def hit_rate(relevance_matrix: list[list[bool]]) -> float:
    """
    Calculate hit rate: percentage of queries where correct document found.

    Args:
        relevance_matrix: List of lists, where each inner list contains bools
                         indicating if result at that rank is correct

    Returns:
        Hit rate as float (0.0 to 1.0)
    """
    cnt = 0
    for line in relevance_matrix:
        if True in line:
            cnt += 1
    return cnt / len(relevance_matrix) if relevance_matrix else 0.0


def mrr(relevance_matrix: list[list[bool]]) -> float:
    """
    Calculate Mean Reciprocal Rank: average of 1/rank of first correct result.

    Args:
        relevance_matrix: List of lists, where each inner list contains bools

    Returns:
        MRR as float (0.0 to 1.0)
    """
    total_score = 0.0
    for line in relevance_matrix:
        for rank in range(len(line)):
            if line[rank] == True:
                total_score += 1.0 / (rank + 1)
                break
    return total_score / len(relevance_matrix) if relevance_matrix else 0.0
```

### 2. **Token Counting Function**

```python
import tiktoken
from typing import Any
import json

def calculate_num_tokens(search_results: list[dict[str, Any]], model: str = "gpt-4o-mini") -> int:
    """
    Calculate total tokens in search results JSON.

    Args:
        search_results: List of search result dictionaries
        model: Model name for tokenizer (default: gpt-4o-mini)

    Returns:
        Number of tokens as int
    """
    encoder = tiktoken.encoding_for_model(model)
    rs_json = json.dumps(search_results)
    return len(encoder.encode(rs_json))
```

### 3. **Scoring Function**

```python
def calculate_score(hit_rate: float, num_tokens: float, alpha: float = 2.0, beta: float = 0.5) -> float:
    """
    Calculate evaluation score: hit_rate^alpha / (num_tokens/1000)^beta

    Args:
        hit_rate: Hit rate (0.0 to 1.0)
        num_tokens: Average number of tokens
        alpha: Exponent for hit rate (default: 2.0)
        beta: Exponent for token penalty (default: 0.5)

    Returns:
        Score as float (higher is better)
    """
    token_penalty = (num_tokens / 1000.0) ** beta
    return (hit_rate ** alpha) / token_penalty if token_penalty > 0 else 0.0
```

### 4. **Parameter Evaluation Function**

```python
from search.search_utils import SearchIndex
from config import SearchType, DEFAULT_SENTENCE_TRANSFORMER_MODEL
from typing import Callable, Any

def evaluate_chunking_params(
    documents: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    chunk_size: int,
    overlap: int,
    top_k: int = 5,
    search_type: str = SearchType.MINSEARCH,
    question_column: str = "question",
    id_column: str = "source",  # or "filename", depending on your ground truth
) -> dict[str, Any]:
    """
    Evaluate chunking parameters by testing search performance.

    Args:
        documents: List of documents to chunk and index
        ground_truth: List of dicts with 'question' and id_column (source/filename)
        chunk_size: Chunk size to test
        overlap: Overlap size to test
        top_k: Number of results to retrieve per query
        search_type: Search type (MINSEARCH or SENTENCE_TRANSFORMERS)
        question_column: Column name for questions in ground truth
        id_column: Column name for correct document ID in ground truth

    Returns:
        Dictionary with:
            - hit_rate: float
            - mrr: float
            - num_tokens: float (average)
            - score: float
            - chunk_size: int
            - overlap: int
            - top_k: int
    """
    # Chunk documents with test parameters
    chunks = chunk_documents(documents, chunk_size=chunk_size, overlap=overlap)

    # Create search index
    index = SearchIndex(
        search_type=search_type,
        text_fields=["content", "title", "source"],
    )

    # Add chunks to index
    index.add_documents(chunks)

    # Evaluate each query in ground truth
    relevance_matrix = []
    token_counts = []

    for gt_item in ground_truth:
        question = gt_item[question_column]
        correct_id = gt_item[id_column]

        # Search with this question
        results = index.search(query=question, num_results=top_k)

        # Check relevance: True if result's source matches correct_id
        relevance = [result.get("source") == correct_id for result in results]
        relevance_matrix.append(relevance)

        # Count tokens
        num_tokens = calculate_num_tokens(results)
        token_counts.append(num_tokens)

    # Calculate metrics
    hr = hit_rate(relevance_matrix)
    mrr_score = mrr(relevance_matrix)
    avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0.0
    score = calculate_score(hr, avg_tokens)

    return {
        "hit_rate": hr,
        "mrr": mrr_score,
        "num_tokens": avg_tokens,
        "score": score,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "top_k": top_k,
    }
```

### 5. **Grid Search Function**

```python
def evaluate_chunking_grid(
    documents: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    chunk_sizes: list[int] = [300, 500, 1000, 2000],
    overlaps: list[int] = [0, 50, 100, 200],
    top_ks: list[int] = [5, 10, 15],
    search_type: str = SearchType.MINSEARCH,
    question_column: str = "question",
    id_column: str = "source",
) -> list[dict[str, Any]]:
    """
    Evaluate all combinations of chunk_size, overlap, and top_k.

    Args:
        documents: List of documents to chunk and index
        ground_truth: List of dicts with questions and correct document IDs
        chunk_sizes: List of chunk sizes to test
        overlaps: List of overlap sizes to test
        top_ks: List of top_k values to test
        search_type: Search type to use
        question_column: Column name for questions
        id_column: Column name for correct document ID

    Returns:
        List of evaluation results (one per combination)
    """
    results = []

    for chunk_size in chunk_sizes:
        for overlap in overlaps:
            # Skip if overlap >= chunk_size (invalid)
            if overlap >= chunk_size:
                continue

            for top_k in top_ks:
                print(f"Evaluating: chunk_size={chunk_size}, overlap={overlap}, top_k={top_k}")

                result = evaluate_chunking_params(
                    documents=documents,
                    ground_truth=ground_truth,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    top_k=top_k,
                    search_type=search_type,
                    question_column=question_column,
                    id_column=id_column,
                )

                results.append(result)
                print(f"  Result: hit_rate={result['hit_rate']:.3f}, "
                      f"mrr={result['mrr']:.3f}, "
                      f"tokens={result['num_tokens']:.1f}, "
                      f"score={result['score']:.3f}")

    return results


def find_best_chunking_params(
    results: list[dict[str, Any]],
    n: int = 5,
) -> list[dict[str, Any]]:
    """
    Find best chunking parameter combinations by score.

    Args:
        results: List of evaluation results from evaluate_chunking_grid
        n: Number of top results to return

    Returns:
        List of top n results sorted by score (descending)
    """
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
    return sorted_results[:n]
```

---

## Dependencies to Add

### New Package Required:
- `tiktoken` - For token counting

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing dependencies ...
    "tiktoken>=0.5.0",
]
```

---

## Ground Truth Data Format

The evaluation functions expect ground truth in this format:

```python
ground_truth = [
    {
        "question": "What causes user frustration?",
        "source": "question_12345",  # or "filename": "doc.pdf"
    },
    {
        "question": "How do users behave when confused?",
        "source": "question_67890",
    },
    # ... more examples
]
```

**Note**: The `id_column` parameter should match your ground truth structure:
- If your ground truth uses `"source"` → `id_column="source"`
- If your ground truth uses `"filename"` → `id_column="filename"`
- Documents must have matching `source` or `filename` field for relevance checking

---

## Usage Example

```python
from search.simple_chunking import evaluate_chunking_grid, find_best_chunking_params

# Load your documents and ground truth
documents = [...]  # Your document list
ground_truth = [...]  # Your ground truth list

# Evaluate all combinations
results = evaluate_chunking_grid(
    documents=documents,
    ground_truth=ground_truth,
    chunk_sizes=[300, 500, 1000, 2000],
    overlaps=[0, 50, 100, 200],
    top_ks=[5, 10, 15],
)

# Find best parameters
best_params = find_best_chunking_params(results, n=5)

# Print best result
print(f"Best configuration:")
print(f"  chunk_size={best_params[0]['chunk_size']}")
print(f"  overlap={best_params[0]['overlap']}")
print(f"  top_k={best_params[0]['top_k']}")
print(f"  score={best_params[0]['score']:.3f}")
print(f"  hit_rate={best_params[0]['hit_rate']:.3f}")
```

---

## Integration Points

### 1. **With SearchIndex**
- Uses `SearchIndex` from `search.search_utils`
- Compatible with both MINSEARCH and SENTENCE_TRANSFORMERS

### 2. **With Config**
- Uses `SearchType` enum from `config`
- Can use different search types for evaluation

### 3. **With TextRAG**
- Could add a method to `TextRAG` class:
  ```python
  def evaluate_chunking(self, ground_truth: list[dict]) -> dict:
      """Evaluate chunking parameters using current config"""
      return evaluate_chunking_params(
          documents=self.documents,  # Would need to store
          ground_truth=ground_truth,
          chunk_size=self.config.chunk_size,
          overlap=self.config.chunk_overlap,
          search_type=self.config.search_type,
      )
  ```

---

## File Structure

```
search/
  simple_chunking.py         # Add all evaluation functions here
  search_utils.py            # (already exists, used by evaluation)
  flexible_search.py         # (already exists, used by evaluation)
```

---

## Considerations

### 1. **Performance**
- Grid search can be slow (evaluates many combinations)
- Each evaluation rebuilds the index
- Consider caching or limiting parameter ranges for initial tests

### 2. **Ground Truth Format**
- Need to match document `source` field with ground truth `id_column`
- Documents from MongoDB use format: `"question_{question_id}"`
- Adjust `id_column` based on your ground truth structure

### 3. **Token Counting**
- Uses `tiktoken` with `gpt-4o-mini` model by default
- Adjust if using different model for token counting

### 4. **Memory**
- Rebuilding index for each parameter combination uses memory
- Consider processing smaller document sets for evaluation

---

## Summary

**What Gets Added:**
1. ✅ `hit_rate()` - Calculate hit rate metric
2. ✅ `mrr()` - Calculate MRR metric
3. ✅ `calculate_num_tokens()` - Count tokens in results
4. ✅ `calculate_score()` - Scoring formula
5. ✅ `evaluate_chunking_params()` - Evaluate single parameter set
6. ✅ `evaluate_chunking_grid()` - Grid search over all combinations
7. ✅ `find_best_chunking_params()` - Find top results

**New Dependency:**
- `tiktoken` package

**Files Modified:**
- `search/simple_chunking.py` - Add all functions above
- `pyproject.toml` - Add `tiktoken` dependency

**Required Data:**
- Ground truth dataset with questions and correct document IDs
