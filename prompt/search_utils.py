# Document search utilities
from typing import Any, Dict, List


class RAGError(Exception):
    """Base exception for RAG-related errors"""

    pass


def search_documents(question: str, index: Any | None = None) -> List[Dict[str, Any]]:
    """
    Search for relevant documents using the provided search index.

    Supports both text-based search (Minsearch) and vector-based search (SentenceTransformers).
    Automatically detects the index type and uses the appropriate search method.

    Args:
        question: The search query/question to find relevant documents for
        index: The search index to query (Minsearch Index or VectorIndex)

    Returns:
        List of relevant document dictionaries with content, filename, and metadata

    Raises:
        RAGError: If question is empty, index is None, or search fails
    """
    try:
        # Basic validation
        if not question or not question.strip():
            raise RAGError("Question cannot be empty")

        if index is None:
            raise RAGError("Search index is required")

        # Check if it's a vector index by checking the class name
        if hasattr(index, "__class__") and "VectorIndex" in str(index.__class__):
            # Vector search (query, num_results)
            results = index.search(question, num_results=5)
        else:
            # Text search (minsearch)
            results = index.search(
                question,
                boost_dict={},
                filter_dict={},
                num_results=5,
            )

        if not results:
            raise RAGError("No documents found for the given question")

        return results

    except RAGError:
        raise
    except Exception as e:
        raise RAGError(f"Search failed: {str(e)}") from e
