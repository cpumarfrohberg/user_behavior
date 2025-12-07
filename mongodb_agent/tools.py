# Tool functions for RAG Agent
"""MongoDB search tool function that agent can call repeatedly"""

import logging
import threading
from typing import List

from pymongo.collection import Collection

from mongodb_agent.models import SearchResult

DEFAULT_NUM_RESULTS = 5
DEFAULT_TOOL_CALL_COUNT = 0
DEFAULT_MAX_TOOL_CALLS = 5
DEFAULT_SCORE = 0.0
MIN_SIMILARITY_SCORE = 0.0
MAX_SIMILARITY_SCORE = 1.0
SCORE_NORMALIZATION_DIVISOR = 10.0
QUERY_LOG_TRUNCATE_LENGTH = 50
MONGODB_EXCLUDE_ID = 0

# Search quality evaluation thresholds (normalized scores 0-1)
MIN_RELEVANT_SCORE = 0.2  # Raw score 2.0
HIGH_QUALITY_SCORE = 0.35  # Raw score 3.5
MIN_RELEVANT_COUNT = 2

# Quality score calculation weights
HIGH_QUALITY_BONUS = 0.3
COUNT_SCORE_WEIGHT = 0.5
SCORE_COMPONENT_WEIGHT = 0.2

logger = logging.getLogger(__name__)


class ToolCallLimitExceeded(RuntimeError):
    """Exception raised when maximum tool calls limit is exceeded."""

    def __init__(self, current_count: int, max_calls: int):
        self.current_count = current_count
        self.max_calls = max_calls
        message = (
            f"🚫 HARD STOP: Maximum tool calls limit ({max_calls}) has been EXCEEDED "
            f"(you have already made {current_count} calls).\n\n"
            f"YOU MUST IMMEDIATELY:\n"
            f"1. STOP making any more tool calls\n"
            f"2. Use the search results from your previous {current_count} successful searches\n"
            f"3. Synthesize your final answer from those previous results\n"
            f"4. Return your answer in the required JSON format\n\n"
            f"Do NOT attempt another search. The limit is enforced and you have already "
            f"exceeded it. Synthesize from what you have."
        )
        super().__init__(message)


class SearchQualityEvaluation:
    """Evaluation result for search quality assessment"""

    def __init__(
        self,
        is_poor: bool,
        quality_score: float,
        relevant_count: int,
        has_high_quality: bool,
        avg_score: float,
    ):
        self.is_poor = is_poor
        self.quality_score = quality_score
        self.relevant_count = relevant_count
        self.has_high_quality = has_high_quality
        self.avg_score = avg_score


# Global state
_mongodb_collection: Collection | None = None
_tool_call_count = DEFAULT_TOOL_CALL_COUNT
_initial_max_tool_calls = DEFAULT_MAX_TOOL_CALLS
_extended_max_tool_calls = DEFAULT_MAX_TOOL_CALLS
_current_max_tool_calls = DEFAULT_MAX_TOOL_CALLS
_enable_adaptive_limit = False
_counter_lock = threading.Lock()


def initialize_mongodb_collection(collection: Collection) -> None:
    global _mongodb_collection
    _mongodb_collection = collection
    logger.info("MongoDB collection initialized for search tool")


def set_max_tool_calls(max_calls: int) -> None:
    global _initial_max_tool_calls, _current_max_tool_calls
    with _counter_lock:
        _initial_max_tool_calls = max_calls
        _current_max_tool_calls = max_calls


def set_adaptive_limit_config(
    initial_limit: int, extended_limit: int, enabled: bool
) -> None:
    global \
        _initial_max_tool_calls, \
        _extended_max_tool_calls, \
        _current_max_tool_calls, \
        _enable_adaptive_limit
    with _counter_lock:
        _initial_max_tool_calls = initial_limit
        _extended_max_tool_calls = extended_limit
        _current_max_tool_calls = initial_limit
        _enable_adaptive_limit = enabled


def reset_tool_call_count() -> None:
    """Reset the tool call counter and limit (called at start of each query)"""
    global _tool_call_count, _current_max_tool_calls
    with _counter_lock:
        _tool_call_count = DEFAULT_TOOL_CALL_COUNT
        _current_max_tool_calls = _initial_max_tool_calls


def get_tool_call_count() -> int:
    global _tool_call_count
    with _counter_lock:
        return _tool_call_count


def _check_and_increment_tool_call_count() -> int:
    """Check limit before incrementing, raise exception if limit reached."""
    global _tool_call_count, _current_max_tool_calls

    with _counter_lock:
        if _tool_call_count >= _current_max_tool_calls:
            logger.warning(
                f"Tool call limit reached: {_tool_call_count} >= {_current_max_tool_calls}. "
                f"Blocking call before it starts."
            )
            raise ToolCallLimitExceeded(_tool_call_count, _current_max_tool_calls)

        _tool_call_count += 1
        logger.info(
            f"✅ Tool call #{_tool_call_count} of {_current_max_tool_calls} allowed"
        )
        return _tool_call_count


def _build_mongodb_query(query: str, tags: List[str] | None) -> dict:
    """Build MongoDB text search query with optional tag filtering."""
    mongo_query: dict = {"$text": {"$search": query}}
    if tags:
        mongo_query["tags"] = {"$in": tags}
    return mongo_query


def _normalize_similarity_score(text_score: float) -> float:
    if text_score <= DEFAULT_SCORE:
        return MIN_SIMILARITY_SCORE
    return min(text_score / SCORE_NORMALIZATION_DIVISOR, MAX_SIMILARITY_SCORE)


def _get_relevant_results(search_results: List[SearchResult]) -> List[SearchResult]:
    return [
        r
        for r in search_results
        if r.similarity_score is not None and r.similarity_score >= MIN_RELEVANT_SCORE
    ]


def _has_high_quality_result(search_results: List[SearchResult]) -> bool:
    return any(
        r.similarity_score is not None and r.similarity_score >= HIGH_QUALITY_SCORE
        for r in search_results
    )


def _calculate_average_score(search_results: List[SearchResult]) -> float:
    scores_with_values = [
        r.similarity_score for r in search_results if r.similarity_score is not None
    ]
    if not scores_with_values:
        return MIN_SIMILARITY_SCORE
    return sum(scores_with_values) / len(scores_with_values)


def _calculate_quality_score(
    relevant_count: int, has_high_quality: bool, avg_score: float
) -> float:
    count_score = min(relevant_count / MIN_RELEVANT_COUNT, MAX_SIMILARITY_SCORE)
    high_quality_bonus = (
        HIGH_QUALITY_BONUS if has_high_quality else MIN_SIMILARITY_SCORE
    )
    score_component = min(avg_score / MAX_SIMILARITY_SCORE, MAX_SIMILARITY_SCORE)

    quality_score = (
        (count_score * COUNT_SCORE_WEIGHT)
        + (score_component * SCORE_COMPONENT_WEIGHT)
        + high_quality_bonus
    )
    return min(quality_score, MAX_SIMILARITY_SCORE)


def _is_poor_quality(relevant_count: int, has_high_quality: bool) -> bool:
    """Determine if results are poor enough to warrant extension."""
    return relevant_count < MIN_RELEVANT_COUNT and not has_high_quality


def evaluate_search_quality(
    search_results: List[SearchResult],
) -> SearchQualityEvaluation:
    """Evaluate if search results are poor quality and warrant limit extension."""
    if not search_results:
        return SearchQualityEvaluation(
            is_poor=True,
            quality_score=MIN_SIMILARITY_SCORE,
            relevant_count=0,
            has_high_quality=False,
            avg_score=MIN_SIMILARITY_SCORE,
        )

    relevant_results = _get_relevant_results(search_results)
    relevant_count = len(relevant_results)
    has_high_quality = _has_high_quality_result(search_results)
    avg_score = _calculate_average_score(search_results)
    quality_score = _calculate_quality_score(
        relevant_count, has_high_quality, avg_score
    )
    is_poor = _is_poor_quality(relevant_count, has_high_quality)

    return SearchQualityEvaluation(
        is_poor=is_poor,
        quality_score=quality_score,
        relevant_count=relevant_count,
        has_high_quality=has_high_quality,
        avg_score=avg_score,
    )


def _convert_doc_to_search_result(doc: dict) -> SearchResult:
    """Convert MongoDB document to SearchResult model."""
    content_parts = []
    if doc.get("title"):
        content_parts.append(doc["title"])
    if doc.get("body"):
        content_parts.append(doc["body"])

    text_score = doc.get("score", DEFAULT_SCORE)
    similarity_score = _normalize_similarity_score(text_score)

    tags_list = doc.get("tags", [])
    if not isinstance(tags_list, list):
        tags_list = []

    return SearchResult(
        content=" ".join(content_parts),
        source=f"question_{doc.get('question_id', 'unknown')}",
        title=doc.get("title"),
        similarity_score=similarity_score,
        tags=tags_list,
    )


def _execute_mongodb_search(
    collection: Collection, query: dict, num_results: int
) -> List[dict]:
    """Execute MongoDB text search query and return raw documents."""
    try:
        cursor = (
            collection.find(
                query,
                {"score": {"$meta": "textScore"}, "_id": MONGODB_EXCLUDE_ID},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(num_results)
        )
        return list(cursor)
    except Exception as e:
        logger.error(f"Error executing MongoDB text search: {e}")
        raise RuntimeError(f"MongoDB search failed: {str(e)}") from e


def search_mongodb(
    query: str, tags: List[str] | None = None, num_results: int = DEFAULT_NUM_RESULTS
) -> List[SearchResult]:
    """
    Search MongoDB for relevant content using text search.

    ⚠️ IMPORTANT LIMIT: You have a maximum of 3 tool calls per query. After 3 calls,
    this tool will raise ToolCallLimitExceeded and you MUST stop and synthesize your answer.
    Most questions can be answered with just 1-2 searches. Be decisive and stop early.

    Args:
        query: Search query string (e.g., "user frustration", "satisfaction patterns")
        tags: Optional list of tags to filter by (e.g., ["user-behavior", "usability"])
        num_results: Number of results to return (default: 5)

    Returns:
        List of search results with content, source, and text search scores.

    Raises:
        RuntimeError: If MongoDB collection is not initialized or search fails
        ToolCallLimitExceeded: If you have exceeded the maximum of 3 tool calls.
    """
    global \
        _tool_call_count, \
        _mongodb_collection, \
        _current_max_tool_calls, \
        _initial_max_tool_calls

    if _mongodb_collection is None:
        raise RuntimeError(
            "MongoDB collection not initialized. Call initialize_mongodb_collection first."
        )

    with _counter_lock:
        if _tool_call_count > _current_max_tool_calls:
            logger.warning(
                f"Counter state suspicious: {_tool_call_count} > {_current_max_tool_calls}. "
                f"This suggests counter wasn't reset between queries. Resetting now."
            )
            _tool_call_count = DEFAULT_TOOL_CALL_COUNT
            _current_max_tool_calls = _initial_max_tool_calls

    _check_and_increment_tool_call_count()

    mongo_query = _build_mongodb_query(query, tags)
    raw_results = _execute_mongodb_search(_mongodb_collection, mongo_query, num_results)
    search_results = [_convert_doc_to_search_result(doc) for doc in raw_results]

    # Check for early stopping criteria
    relevant_results = _get_relevant_results(search_results)
    has_high_quality = _has_high_quality_result(search_results)

    if len(relevant_results) >= MIN_RELEVANT_COUNT or has_high_quality:
        logger.info(
            f"✅ GOOD RESULTS FOUND: {len(relevant_results)} relevant results, "
            f"high_quality={has_high_quality}. Agent should consider stopping early."
        )
    else:
        logger.info(
            f"MongoDB search returned {len(search_results)} results "
            f"({len(relevant_results)} relevant) for query: {query[:QUERY_LOG_TRUNCATE_LENGTH]}"
        )

    return search_results
