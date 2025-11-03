# Tool functions for RAG Agent
"""Search tool function that agent can call repeatedly"""

from typing import List

from source.models import SearchResult

# Global search index (loaded once, used by tool)
_search_index = None


def initialize_search_index(search_index) -> None:
    """
    Pre-load documents into search index.

    This should be called once before the agent starts making tool calls.

    Args:
        search_index: Initialized SearchIndex instance with documents loaded
    """
    global _search_index
    _search_index = search_index


def search_documents(query: str, num_results: int = 5) -> List[SearchResult]:
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
        RuntimeError: If search index is not initialized
    """
    if _search_index is None:
        raise RuntimeError(
            "Search index not initialized. Call initialize_search_index first."
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
