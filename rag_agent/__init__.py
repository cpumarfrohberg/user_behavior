# RAG Agent package for making repetitive tool calls
"""RAG Agent that makes multiple tool calls for better retrieval"""

from rag_agent.agent import RAGAgent
from rag_agent.tools import initialize_search_index, search_documents

__all__ = [
    "RAGAgent",
    "search_documents",
    "initialize_search_index",
]
