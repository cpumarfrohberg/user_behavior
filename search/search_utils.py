# Search utilities for banking RAG system - simplified with flexible search
import logging
from typing import Any, Dict, List, Optional

from config import (
    DEFAULT_NUM_RESULTS,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    SearchType,
)

from .flexible_search import FlexibleSearch, RAGError

logger = logging.getLogger(__name__)


class SearchIndex:
    """Simplified search index wrapper using FlexibleSearch"""

    def __init__(
        self,
        search_type: str = SearchType.MINSEARCH.value,
        model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL,
        text_fields: Optional[List[str]] = None,
    ):
        # Map old search types to new methods
        method_map = {
            SearchType.MINSEARCH.value: "minsearch",
            SearchType.SENTENCE_TRANSFORMERS.value: "sentence_transformers",
        }

        # Default to minsearch for new searches
        method = method_map.get(search_type, "minsearch")

        self.flexible_search = FlexibleSearch(
            method=method,
            model_name=model_name,
            text_fields=text_fields,
        )

        # Keep old interface for compatibility
        self.search_type = search_type
        self.model_name = model_name
        self.text_fields = text_fields or ["content", "title", "tags", "source"]

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to the search index"""
        self.flexible_search.add_documents(documents)

    def search(
        self,
        query: str,
        num_results: int = DEFAULT_NUM_RESULTS,
        boost_dict: Optional[Dict[str, float]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search the index for relevant documents"""
        return self.flexible_search.search(query, num_results, boost_dict, filter_dict)


def search_documents(
    query: str,
    index: SearchIndex,
    num_results: int = DEFAULT_NUM_RESULTS,
    boost_dict: Optional[Dict[str, float]] = None,
    filter_dict: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Convenience function to search documents"""
    if index is None:
        raise RAGError("Search index is required")

    return index.search(
        query=query,
        num_results=num_results,
        boost_dict=boost_dict,
        filter_dict=filter_dict,
    )
