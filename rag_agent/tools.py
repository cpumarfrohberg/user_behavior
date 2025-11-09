# Tool functions for RAG Agent
"""Search tool function that agent can call repeatedly"""

from typing import List

from rag_agent.models import SearchResult

# Global search index (loaded once, used by tool)
_search_index = None
# Global tool call counter (incremented by agent's event handler)
_tool_call_count = 0
_max_tool_calls = 5  # Safety limit - can be overridden


def initialize_search_index(search_index) -> None:
    """
    Pre-load documents into search index.

    This should be called once before the agent starts making tool calls.

    Args:
        search_index: Initialized SearchIndex instance with documents loaded
    """
    global _search_index
    _search_index = search_index


def set_max_tool_calls(max_calls: int) -> None:
    """Set the maximum number of tool calls allowed"""
    global _max_tool_calls
    _max_tool_calls = max_calls


def reset_tool_call_count() -> None:
    """Reset the tool call counter (called at start of each query)"""
    global _tool_call_count
    _tool_call_count = 0


def search_documents(query: str, num_results: int = 2) -> List[SearchResult]:
    """
    Search the document index for relevant content.

    Use this tool to find information about user behavior patterns,
    questions, answers, and discussions from StackExchange.

    Args:
        query: Search query string (e.g., "user frustration", "satisfaction patterns")
        num_results: Number of results to return (default: 5)

    Returns:
        List of search results with content, source, similarity scores

    Raises:
        RuntimeError: If search index is not initialized or max tool calls exceeded
    """
    global _tool_call_count, _max_tool_calls

    if _search_index is None:
        raise RuntimeError(
            "Search index not initialized. Call initialize_search_index first."
        )

    _tool_call_count += 1
    if _tool_call_count > _max_tool_calls:
        raise RuntimeError(
            f"Maximum tool calls ({_max_tool_calls}) exceeded. "
            f"Please stop searching and provide your answer based on the previous searches."
        )

    results = _search_index.search(query=query, num_results=num_results)

    # Convert to SearchResult models
    search_results = []
    for doc in results:
        # Handle tags: convert string to list if needed (MinSearch returns tags as strings)
        tags = doc.get("tags", [])
        if isinstance(tags, str):
            # Convert space-separated string to list
            tags = [tag.strip() for tag in tags.split() if tag.strip()]
        elif not isinstance(tags, list):
            tags = []

        search_results.append(
            SearchResult(
                content=doc.get("content", ""),
                source=doc.get("source", "unknown"),
                title=doc.get("title"),
                similarity_score=doc.get("similarity_score"),
                tags=tags,
            )
        )

    return search_results
