# Simplified search system - Minsearch and SentenceTransformers only
import logging
from typing import Any

import numpy as np
from minsearch import Index
from sentence_transformers import SentenceTransformer

from config import (
    DEFAULT_NUM_RESULTS,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
)

logger = logging.getLogger(__name__)


class RAGError(Exception):
    """Base exception for RAG-related errors"""

    pass


class FlexibleSearch:
    """Simplified search with Minsearch and SentenceTransformers only"""

    def __init__(
        self,
        method: str = "minsearch",
        model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL,
        text_fields: list[str] | None = None,
    ):
        self.method = method
        self.model_name = model_name
        self.text_fields = text_fields or ["content", "title", "tags", "source"]
        self.documents = []

        # Initialize components based on method
        self.minsearch_index = None
        self.embedder = None

        if method == "minsearch":
            self.minsearch_index = Index(text_fields=self.text_fields)
        elif method == "sentence_transformers":
            try:
                self.embedder = SentenceTransformer(model_name)
                logger.info(f"Initialized SentenceTransformer with model: {model_name}")
            except ImportError:
                raise RAGError(
                    "sentence-transformers is required for vector search. "
                    "Install it with: pip install sentence-transformers"
                )
        else:
            raise RAGError(f"Unsupported search method: {method}")

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        """Add documents to search index"""
        try:
            if not documents:
                logger.warning("No documents provided to add to index")
                return

            self.documents.extend(documents)

            if self.method == "minsearch":
                self.minsearch_index.fit(documents)
            elif self.method == "sentence_transformers":
                # Generate embeddings for all documents
                contents = [doc.get("content", "") for doc in documents]
                embeddings = self.embedder.encode(contents)
                # Store embeddings with documents
                for i, doc in enumerate(documents):
                    doc["_embedding"] = embeddings[i]

            logger.info(
                f"Added {len(documents)} documents to {self.method} search index"
            )

        except Exception as e:
            logger.error(f"Error adding documents to index: {e}")
            raise RAGError(f"Failed to add documents: {str(e)}")

    def search(
        self,
        query: str,
        num_results: int = DEFAULT_NUM_RESULTS,
        boost_dict: dict[str, float] | None = None,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search using the selected method"""
        try:
            if not query or not query.strip():
                raise RAGError("Search query cannot be empty")

            if not self.documents:
                logger.warning("No documents in index to search")
                return []

            if self.method == "minsearch":
                return self._minsearch_search(
                    query, num_results, boost_dict, filter_dict
                )
            elif self.method == "sentence_transformers":
                return self._sentence_transformers_search(query, num_results)
            else:
                raise RAGError(f"Unsupported search method: {self.method}")

        except RAGError:
            raise
        except Exception as e:
            logger.error(f"Error during search: {e}")
            raise RAGError(f"Search failed: {str(e)}")

    def _minsearch_search(
        self,
        query: str,
        num_results: int,
        boost_dict: dict[str, float] | None = None,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Minsearch text-based search"""
        if self.minsearch_index is None:
            raise RAGError("Minsearch index not initialized")

        try:
            boost_dict = boost_dict or {}
            filter_dict = filter_dict or {}

            results = self.minsearch_index.search(
                query,
                boost_dict=boost_dict,
                filter_dict=filter_dict,
                num_results=num_results,
            )

            # Add similarity scores (text search doesn't have them naturally)
            for i, result in enumerate(results):
                result["similarity_score"] = 1.0 - (i * 0.1)  # Decreasing scores

            logger.debug(f"Minsearch returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Minsearch failed: {e}")
            raise RAGError(f"Minsearch error: {str(e)}")

    def _sentence_transformers_search(
        self, query: str, num_results: int
    ) -> list[dict[str, Any]]:
        """SentenceTransformers vector search"""
        if self.embedder is None:
            raise RAGError("SentenceTransformer model not initialized")

        try:
            # Generate query embedding
            query_embedding = self.embedder.encode([query])

            # Calculate similarities
            similarities = []
            for doc in self.documents:
                if "_embedding" not in doc:
                    doc["_embedding"] = self.embedder.encode([doc.get("content", "")])[
                        0
                    ]

                similarity = np.dot(doc["_embedding"], query_embedding.T).flatten()[0]
                similarities.append((doc, similarity))

            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x[1], reverse=True)
            results = []

            for doc, similarity in similarities[:num_results]:
                result = doc.copy()
                result["similarity_score"] = float(similarity)
                results.append(result)

            logger.debug(f"SentenceTransformers search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"SentenceTransformers search failed: {e}")
            raise RAGError(f"SentenceTransformers search error: {str(e)}")
