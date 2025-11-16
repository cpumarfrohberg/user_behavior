# Tool functions for RAG Agent
"""MongoDB search tool function that agent can call repeatedly"""

import logging
from typing import List

from pymongo.collection import Collection

from mongodb_agent.models import SearchResult

logger = logging.getLogger(__name__)

# Global MongoDB collection (set during initialization)
_mongodb_collection: Collection | None = None
# Global tool call counter (incremented by agent's event handler)
_tool_call_count = 0
_max_tool_calls = 5  # Safety limit - can be overridden


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
    _tool_call_count = 0


def search_mongodb(
    query: str, tags: List[str] | None = None, num_results: int = 5
) -> List[SearchResult]:
    """
    Search MongoDB for relevant content using text search.

    Use this tool to find information about user behavior patterns,
    questions, answers, and discussions from StackExchange.

    Args:
        query: Search query string (e.g., "user frustration", "satisfaction patterns")
        tags: Optional list of tags to filter by (e.g., ["user-behavior", "usability"])
        num_results: Number of results to return (default: 5)

    Returns:
        List of search results with content, source, and text search scores

    Raises:
        RuntimeError: If MongoDB collection is not initialized or max tool calls exceeded
    """
    global _tool_call_count, _max_tool_calls, _mongodb_collection

    if _mongodb_collection is None:
        raise RuntimeError(
            "MongoDB collection not initialized. Call initialize_mongodb_collection first."
        )

    if _tool_call_count >= _max_tool_calls:
        raise RuntimeError(
            f"Maximum tool calls ({_max_tool_calls}) exceeded. "
            f"Please stop searching and provide your answer based on the previous searches."
        )

    _tool_call_count += 1

    # Build MongoDB query
    mongo_query: dict = {"$text": {"$search": query}}

    # Add tag filtering if provided
    if tags:
        mongo_query["tags"] = {"$in": tags}

    try:
        # Execute MongoDB text search with scoring
        cursor = (
            _mongodb_collection.find(
                mongo_query,
                {"score": {"$meta": "textScore"}, "_id": 0},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(num_results)
        )

        results = list(cursor)

        # Convert MongoDB documents to SearchResult models
        search_results = []
        for doc in results:
            # Combine title and body for content
            content_parts = []
            if doc.get("title"):
                content_parts.append(doc["title"])
            if doc.get("body"):
                content_parts.append(doc["body"])

            # Get text search score (normalize to 0-1 range for similarity_score)
            text_score = doc.get("score", 0.0)
            # MongoDB text scores can vary, normalize if needed
            # For now, use score directly (can be > 1.0)
            similarity_score = min(text_score / 10.0, 1.0) if text_score > 0 else 0.0

            # Handle tags
            tags_list = doc.get("tags", [])
            if not isinstance(tags_list, list):
                tags_list = []

            search_results.append(
                SearchResult(
                    content=" ".join(content_parts),
                    source=f"question_{doc.get('question_id', 'unknown')}",
                    title=doc.get("title"),
                    similarity_score=similarity_score,
                    tags=tags_list,
                )
            )

        logger.info(
            f"MongoDB search returned {len(search_results)} results for query: {query[:50]}"
        )
        return search_results

    except Exception as e:
        logger.error(f"Error executing MongoDB text search: {e}")
        raise RuntimeError(f"MongoDB search failed: {str(e)}") from e
