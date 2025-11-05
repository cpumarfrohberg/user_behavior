"""Tests for RAG Agent tools"""

import pytest

from config import SearchType
from rag_agent.models import SearchResult
from rag_agent.tools import initialize_search_index, search_documents
from search.search_utils import SearchIndex


@pytest.fixture
def mock_search_index():
    """Create a mock search index with sample documents"""
    index = SearchIndex(search_type=SearchType.MINSEARCH)

    # Add sample documents
    # Note: tags must be a string for MinSearch (not a list)
    sample_docs = [
        {
            "content": "Users often express frustration when interfaces are slow to respond.",
            "source": "question_123",
            "title": "Why do users get frustrated?",
            "tags": "user-behavior frustration",  # Converted to string
        },
        {
            "content": "Satisfaction is measured through user feedback and surveys.",
            "source": "question_456",
            "title": "Measuring user satisfaction",
            "tags": "user-behavior satisfaction",  # Converted to string
        },
        {
            "content": "Usability issues include confusing navigation and unclear labels.",
            "source": "question_789",
            "title": "Common usability problems",
            "tags": "usability user-experience",  # Converted to string
        },
    ]

    index.add_documents(sample_docs)
    return index


def test_initialize_search_index(mock_search_index):
    """Test initialize_search_index sets global index"""
    initialize_search_index(mock_search_index)

    # Verify we can call search_documents now
    results = search_documents("user frustration", num_results=2)

    assert len(results) > 0
    assert isinstance(results[0], SearchResult)


def test_search_documents_returns_results(mock_search_index):
    """Test search_documents returns SearchResult objects"""
    initialize_search_index(mock_search_index)

    results = search_documents("user frustration", num_results=2)

    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(result, SearchResult) for result in results)

    # Verify SearchResult structure
    result = results[0]
    assert result.content is not None
    assert result.source is not None


def test_search_documents_handles_empty_index():
    """Test search_documents handles uninitialized index"""
    # Import the global _search_index to reset it
    # Temporarily set to None to test error handling
    import rag_agent.tools as tools_module
    from rag_agent.tools import _search_index

    original_index = tools_module._search_index
    tools_module._search_index = None

    try:
        with pytest.raises(RuntimeError, match="Search index not initialized"):
            search_documents("test query", num_results=1)
    finally:
        # Restore original index
        tools_module._search_index = original_index


def test_search_documents_num_results(mock_search_index):
    """Test search_documents respects num_results parameter"""
    initialize_search_index(mock_search_index)

    results_3 = search_documents("user", num_results=3)
    results_1 = search_documents("user", num_results=1)

    assert len(results_3) <= 3
    assert len(results_1) <= 1


def test_search_documents_result_structure(mock_search_index):
    """Test search_documents returns properly structured results"""
    initialize_search_index(mock_search_index)

    results = search_documents("satisfaction", num_results=2)

    for result in results:
        assert isinstance(result, SearchResult)
        assert result.content is not None
        assert isinstance(result.content, str)
        assert len(result.content) > 0
