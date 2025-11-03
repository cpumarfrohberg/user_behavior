# Models for RAG Agent (reuse existing models)
"""Re-export existing models for agent use"""

from source.models import RAGAnswer, SearchResult

__all__ = ["RAGAnswer", "SearchResult"]
