# Tool functions for RAG Agent
"""MongoDB search tool function that agent can call repeatedly"""

import logging
from typing import List

from pymongo.collection import Collection

from mongodb_agent.models import SearchResult

logger = logging.getLogger(__name__)


class ToolCallLimitExceeded(RuntimeError):
    """
    Exception raised when the maximum number of tool calls has been exceeded.

    This is a HARD STOP - the agent MUST stop making tool calls and synthesize
    an answer from the previous search results. Do NOT attempt to make another
    tool call after receiving this exception.
    """

    def __init__(self, current_count: int, max_calls: int):
        self.current_count = current_count
        self.max_calls = max_calls
        message = (
            f"🚫 HARD STOP: Maximum tool calls limit ({max_calls}) has been EXCEEDED "
            f"(you made {current_count} calls).\n\n"
            f"YOU MUST IMMEDIATELY:\n"
            f"1. STOP making any more tool calls\n"
            f"2. Use the search results from your previous {current_count - 1} successful searches\n"
            f"3. Synthesize your final answer from those previous results\n"
            f"4. Return your answer in the required JSON format\n\n"
            f"Do NOT attempt another search. The limit is enforced and you have already "
            f"exceeded it. Synthesize from what you have."
        )
        super().__init__(message)


# Constants
DEFAULT_NUM_RESULTS = 5  # Default number of search results to return
DEFAULT_TOOL_CALL_COUNT = 0  # Initial/reset value for tool call counter
DEFAULT_MAX_TOOL_CALLS = 5  # Safety limit - can be overridden via set_max_tool_calls()
DEFAULT_SCORE = 0.0  # Default score value when not present
MIN_SIMILARITY_SCORE = 0.0  # Minimum similarity score
MAX_SIMILARITY_SCORE = 1.0  # Maximum similarity score
SCORE_NORMALIZATION_DIVISOR = 10.0  # Divisor for normalizing MongoDB text scores
QUERY_LOG_TRUNCATE_LENGTH = 50  # Maximum length for query in log messages
MONGODB_EXCLUDE_ID = 0  # MongoDB projection value to exclude _id field

# Global MongoDB collection (set during initialization)
_mongodb_collection: Collection | None = None
# Global tool call counter (incremented by agent's event handler)
_tool_call_count = DEFAULT_TOOL_CALL_COUNT
_max_tool_calls = DEFAULT_MAX_TOOL_CALLS  # Safety limit - can be overridden


def initialize_mongodb_collection(collection: Collection) -> None:
    """
    Initialize MongoDB collection for tool to use.

    This should be called once before the agent starts making tool calls.

    Args:
        collection: MongoDB collection instance
    """
    global _mongodb_collection
    _mongodb_collection = collection
    logger.info("MongoDB collection initialized for search tool")


def set_max_tool_calls(max_calls: int) -> None:
    """Set the maximum number of tool calls allowed"""
    global _max_tool_calls
    _max_tool_calls = max_calls


def reset_tool_call_count() -> None:
    """Reset the tool call counter (called at start of each query)"""
    global _tool_call_count
    _tool_call_count = DEFAULT_TOOL_CALL_COUNT


def increment_tool_call_count() -> int:
    """
    Increment the tool call counter and return the new count.

    This should be called by the event handler when a tool is invoked,
    ensuring the counter is synchronized with actual tool calls.

    Returns:
        The new tool call count after incrementing
    """
    global _tool_call_count
    _tool_call_count += 1
    return _tool_call_count


def _check_tool_call_limit() -> None:
    """
    Check if tool call limit has been exceeded and raise exception if so.

    Note: Counter is incremented by event handler before this check, so we check
    if count > max (not >=) to allow exactly max_tool_calls calls.

    Raises:
        ToolCallLimitExceeded: If maximum tool calls limit has been exceeded
    """
    global _tool_call_count, _max_tool_calls

    if _tool_call_count > _max_tool_calls:
        logger.warning(
            f"Maximum tool calls ({_max_tool_calls}) exceeded (current: {_tool_call_count}). "
            f"Raising ToolCallLimitExceeded - agent MUST STOP and synthesize from previous searches."
        )
        raise ToolCallLimitExceeded(_tool_call_count, _max_tool_calls)


def _build_mongodb_query(query: str, tags: List[str] | None) -> dict:
    """
    Build MongoDB text search query with optional tag filtering.

    Args:
        query: Search query string
        tags: Optional list of tags to filter by

    Returns:
        MongoDB query dictionary
    """
    mongo_query: dict = {"$text": {"$search": query}}

    if tags:
        mongo_query["tags"] = {"$in": tags}

    return mongo_query


def _normalize_similarity_score(text_score: float) -> float:
    """
    Normalize MongoDB text search score to 0-1 range.

    Args:
        text_score: Raw MongoDB text search score

    Returns:
        Normalized similarity score between 0.0 and 1.0
    """
    if text_score <= DEFAULT_SCORE:
        return MIN_SIMILARITY_SCORE

    normalized = min(text_score / SCORE_NORMALIZATION_DIVISOR, MAX_SIMILARITY_SCORE)
    return normalized


def _convert_doc_to_search_result(doc: dict) -> SearchResult:
    """
    Convert MongoDB document to SearchResult model.

    Args:
        doc: MongoDB document with title, body, score, question_id, tags

    Returns:
        SearchResult model instance
    """
    # Combine title and body for content
    content_parts = []
    if doc.get("title"):
        content_parts.append(doc["title"])
    if doc.get("body"):
        content_parts.append(doc["body"])

    # Normalize text search score
    text_score = doc.get("score", DEFAULT_SCORE)
    similarity_score = _normalize_similarity_score(text_score)

    # Handle tags - ensure it's a list
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
    """
    Execute MongoDB text search query and return raw documents.

    Args:
        collection: MongoDB collection instance
        query: MongoDB query dictionary
        num_results: Maximum number of results to return

    Returns:
        List of MongoDB documents

    Raises:
        RuntimeError: If MongoDB search fails
    """
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

    Use this tool to find information about user behavior patterns,
    questions, answers, and discussions from StackExchange.

    ⚠️ IMPORTANT LIMIT: You have a maximum of 3 tool calls per query. After 3 calls,
    this tool will raise ToolCallLimitExceeded and you MUST stop and synthesize your answer.
    Most questions can be answered with just 1-2 searches. Be decisive and stop early.

    Args:
        query: Search query string (e.g., "user frustration", "satisfaction patterns")
        tags: Optional list of tags to filter by (e.g., ["user-behavior", "usability"])
        num_results: Number of results to return (default: 5)

    Returns:
        List of search results with content, source, and text search scores.
        Each result includes: content, source (question_ID), title, similarity_score, tags.

    Raises:
        RuntimeError: If MongoDB collection is not initialized or search fails
        ToolCallLimitExceeded: If you have exceeded the maximum of 3 tool calls.
            When this exception is raised:
            - STOP immediately - do NOT make another tool call
            - Use the results from your previous successful searches
            - Synthesize your answer from those previous results
            - Return your answer in the required JSON format
            This is a HARD LIMIT enforced by the system.
    """
    global _tool_call_count, _mongodb_collection

    # Validate collection is initialized
    if _mongodb_collection is None:
        raise RuntimeError(
            "MongoDB collection not initialized. Call initialize_mongodb_collection first."
        )

    # Check and enforce tool call limit
    # Note: Counter is incremented by event handler in agent.py, so we just check here
    _check_tool_call_limit()

    # Build query, execute search, and transform results
    mongo_query = _build_mongodb_query(query, tags)
    raw_results = _execute_mongodb_search(_mongodb_collection, mongo_query, num_results)
    search_results = [_convert_doc_to_search_result(doc) for doc in raw_results]

    logger.info(
        f"MongoDB search returned {len(search_results)} results for query: {query[:QUERY_LOG_TRUNCATE_LENGTH]}"
    )
    return search_results
