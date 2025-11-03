# Simple chunking utilities - your approach
import json
import random
from typing import Any

import numpy as np
import tiktoken

from config import (
    DEFAULT_BEST_RESULTS_COUNT,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_SOURCE,
    DEFAULT_CHUNK_TITLE,
    DEFAULT_GRID_SEARCH_SAMPLES,
    DEFAULT_GROUND_TRUTH_ID_COLUMN,
    DEFAULT_GROUND_TRUTH_QUESTION_COLUMN,
    DEFAULT_SCORE_ALPHA,
    DEFAULT_SCORE_BETA,
    DEFAULT_SEARCH_TEXT_FIELDS,
    DEFAULT_SEARCH_TYPE,
    DEFAULT_TOKEN_NORMALIZATION_DIVISOR,
    DEFAULT_TOKENIZER_ENCODING_FALLBACK,
    DEFAULT_TOKENIZER_MODEL,
    DEFAULT_TOP_K,
    SearchType,
    TokenizerEncoding,
    TokenizerModel,
)
from search.search_utils import SearchIndex


def _chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Simple text chunking - helper function"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def chunk_documents(
    documents: list[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Chunk documents using simple approach"""
    chunks = []

    for doc in documents:
        content = doc.get("content", "")
        text_chunks = _chunk_text(content, chunk_size, overlap)

        for i, chunk_content in enumerate(text_chunks):
            chunk = {
                "content": chunk_content,
                "title": doc.get("title", DEFAULT_CHUNK_TITLE),
                "source": doc.get("source", DEFAULT_CHUNK_SOURCE),
                "chunk_index": i,
            }
            chunks.append(chunk)

    return chunks


# Evaluation metrics for chunking parameter optimization (private helpers)


def _hit_rate(relevance_matrix: list[list[bool]]) -> float:
    """
    Calculate hit rate: percentage of queries where correct document found.

    Hit rate is the proportion of queries where the correct document appears
    anywhere in the search results (regardless of rank).

    Args:
        relevance_matrix: List of lists, where each inner list contains bools
                         indicating if result at that rank is correct.
                         Example: [[True, False, False], [False, True, False]]
                         means first query found correct doc at rank 0,
                         second query found it at rank 1.

    Returns:
        Hit rate as float (0.0 to 1.0). 1.0 means all queries found correct doc.
    """
    if not relevance_matrix:
        return 0.0

    cnt = 0
    for line in relevance_matrix:
        if True in line:
            cnt += 1

    return cnt / len(relevance_matrix)


def _mrr(relevance_matrix: list[list[bool]]) -> float:
    """
    Calculate Mean Reciprocal Rank: average of 1/rank of first correct result.

    MRR measures how well the system ranks relevant documents. It's the average
    of the reciprocal rank of the first correct document for each query.
    - If correct doc is at rank 1: score = 1/1 = 1.0
    - If correct doc is at rank 2: score = 1/2 = 0.5
    - If correct doc is at rank 3: score = 1/3 = 0.333...
    - If not found: score = 0.0

    Args:
        relevance_matrix: List of lists, where each inner list contains bools
                         indicating if result at that rank is correct.
                         Example: [[True, False, False], [False, True, False], [False, False, False]]
                         means:
                         - Query 1: found at rank 0 → reciprocal rank = 1/1 = 1.0
                         - Query 2: found at rank 1 → reciprocal rank = 1/2 = 0.5
                         - Query 3: not found → reciprocal rank = 0.0
                         - MRR = (1.0 + 0.5 + 0.0) / 3 = 0.5

    Returns:
        MRR as float (0.0 to 1.0). Higher is better. 1.0 means all correct docs at rank 1.
    """
    if not relevance_matrix:
        return 0.0

    total_score = 0.0
    for line in relevance_matrix:
        for rank in range(len(line)):
            if line[rank] is True:
                total_score += 1.0 / (rank + 1)
                break

    return total_score / len(relevance_matrix)


def _calculate_num_tokens(
    search_results: list[dict[str, Any]],
    model: str | TokenizerModel = DEFAULT_TOKENIZER_MODEL,
) -> int:
    """
    Calculate total tokens in search results JSON.

    Counts the number of tokens that would be consumed if the search results
    were sent to an LLM. This helps evaluate the cost/efficiency trade-off
    when optimizing chunking parameters.

    Args:
        search_results: List of search result dictionaries to count tokens for.
                      Each dict typically contains 'content', 'title', 'source', etc.
        model: Model name for tokenizer (default: TokenizerModel.GPT_4O_MINI).
               This determines the tokenization scheme used.
               Can be TokenizerModel enum or string.

    Returns:
        Number of tokens as int

    Example:
        results = [
            {"content": "Some text", "source": "doc1"},
            {"content": "More text", "source": "doc2"}
        ]
        tokens = calculate_num_tokens(results)
        # Returns total token count when JSON-serialized
    """
    # Convert enum to string (StrEnum values are strings, but explicit conversion for clarity)
    model_str = str(model)
    fallback_str = str(DEFAULT_TOKENIZER_ENCODING_FALLBACK)

    try:
        encoder = tiktoken.encoding_for_model(model_str)
    except KeyError:
        # Fallback encoding if model not found
        encoder = tiktoken.get_encoding(fallback_str)

    # Remove non-serializable fields (like numpy arrays/embeddings) before JSON serialization
    serializable_results = []
    for result in search_results:
        serializable_result = {}
        for k, v in result.items():
            # Skip numpy arrays and embeddings which aren't JSON serializable
            if k == "_embedding" or isinstance(v, np.ndarray):
                continue
            serializable_result[k] = v
        serializable_results.append(serializable_result)

    rs_json = json.dumps(serializable_results)
    return len(encoder.encode(rs_json))


def _calculate_score(
    hit_rate: float,
    num_tokens: float,
    alpha: float = DEFAULT_SCORE_ALPHA,
    beta: float = DEFAULT_SCORE_BETA,
) -> float:
    """
    Calculate evaluation score: hit_rate^alpha / (num_tokens/1000)^beta

    Combines accuracy (hit_rate) and efficiency (num_tokens) into a single score.
    Higher hit rates improve score (non-linearly via alpha=2.0).
    Higher tokens penalize score (sub-linearly via beta=0.5).

    Args:
        hit_rate: Hit rate (0.0 to 1.0) - proportion of queries with correct doc found
        num_tokens: Average number of tokens in search results
        alpha: Exponent for hit rate (default: 2.0) - higher prioritizes accuracy
        beta: Exponent for token penalty (default: 0.5) - higher penalizes tokens more

    Returns:
        Score as float (higher is better)
    """
    if hit_rate < 0.0 or hit_rate > 1.0:
        raise ValueError(f"hit_rate must be between 0.0 and 1.0, got {hit_rate}")

    if num_tokens < 0.0:
        raise ValueError(f"num_tokens must be non-negative, got {num_tokens}")

    if hit_rate == 0.0:
        return 0.0

    # Normalize tokens for scaling
    token_penalty = (num_tokens / DEFAULT_TOKEN_NORMALIZATION_DIVISOR) ** beta

    # Avoid division by zero
    if token_penalty <= 0.0:
        return 0.0

    # Calculate score: hit_rate^alpha / token_penalty
    score = (hit_rate**alpha) / token_penalty

    return score


def evaluate_chunking_params(
    documents: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    chunk_size: int,
    overlap: int,
    top_k: int = DEFAULT_TOP_K,
    search_type: str = DEFAULT_SEARCH_TYPE,
    question_column: str = DEFAULT_GROUND_TRUTH_QUESTION_COLUMN,
    id_column: str = DEFAULT_GROUND_TRUTH_ID_COLUMN,
) -> dict[str, Any]:
    """
    Evaluate chunking parameters by testing search performance.

    Tests a single configuration (chunk_size, overlap, top_k) with ground truth.
    Returns metrics: hit_rate, mrr, num_tokens, score, and tested parameters.
    """
    # Chunk documents with test parameters
    chunks = chunk_documents(documents, chunk_size=chunk_size, overlap=overlap)

    # Create search index
    index = SearchIndex(
        search_type=search_type,
        text_fields=DEFAULT_SEARCH_TEXT_FIELDS,
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
        num_tokens = _calculate_num_tokens(results)
        token_counts.append(num_tokens)

    # Calculate metrics
    hr = _hit_rate(relevance_matrix)
    mrr_score = _mrr(relevance_matrix)
    avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0.0
    score = _calculate_score(hr, avg_tokens)

    return {
        "hit_rate": hr,
        "mrr": mrr_score,
        "num_tokens": avg_tokens,
        "score": score,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "top_k": top_k,
        "search_type": str(search_type),
    }


def evaluate_chunking_grid(
    documents: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    chunk_sizes: list[int],
    overlaps: list[int],
    top_ks: list[int],
    n_samples: int = DEFAULT_GRID_SEARCH_SAMPLES,
    search_type: str = DEFAULT_SEARCH_TYPE,
    question_column: str = DEFAULT_GROUND_TRUTH_QUESTION_COLUMN,
    id_column: str = DEFAULT_GROUND_TRUTH_ID_COLUMN,
    random_seed: int | None = None,
) -> list[dict[str, Any]]:
    """
    Evaluate random combinations of chunk_size, overlap, and top_k.

    Generates all valid combinations, then randomly samples n_samples to test.
    Much faster than full grid search while still exploring parameter space.

    Args:
        documents: List of documents to chunk and index
        ground_truth: List of dicts with questions and correct document IDs
        chunk_sizes: List of chunk sizes to consider
        overlaps: List of overlap sizes to consider
        top_ks: List of top_k values to consider
        n_samples: Number of random combinations to test (default: 10)
        search_type: Search type to use
        question_column: Column name for questions
        id_column: Column name for correct document ID
        random_seed: Random seed for reproducibility (default: None)

    Returns:
        List of evaluation results (one per sampled combination)
    """
    if random_seed is not None:
        random.seed(random_seed)

    # Generate all valid combinations (overlap must be < chunk_size)
    valid_combinations = []
    for chunk_size in chunk_sizes:
        for overlap in overlaps:
            if overlap >= chunk_size:
                continue
            for top_k in top_ks:
                valid_combinations.append((chunk_size, overlap, top_k))

    # Sample random combinations
    if n_samples >= len(valid_combinations):
        selected = valid_combinations
    else:
        selected = random.sample(valid_combinations, n_samples)

    # Evaluate each selected combination
    results = []
    for i, (chunk_size, overlap, top_k) in enumerate(selected, 1):
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

    return results


def find_best_chunking_params(
    results: list[dict[str, Any]],
    n: int = DEFAULT_BEST_RESULTS_COUNT,
) -> list[dict[str, Any]]:
    """
    Find best chunking parameter combinations by score.

    Args:
        results: List of evaluation results from evaluate_chunking_grid or evaluate_chunking_params
        n: Number of top results to return

    Returns:
        List of top n results sorted by score (descending)
    """
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
    return sorted_results[:n]
