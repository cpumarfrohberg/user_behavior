# Vector search implementation using SentenceTransformers
from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer


class VectorIndex:
    """Vector-based search index using SentenceTransformers embeddings"""

    def __init__(self, model: SentenceTransformer, chunks: List[Dict[str, Any]]):
        self.model = model
        self.chunks = chunks
        self.embeddings = None
        self._build_index()

    def _build_index(self):
        """Build the vector index by computing embeddings for all chunks"""
        print("🔄 Computing embeddings for vector search...")

        # Extract text content from chunks
        texts = []
        for chunk in self.chunks:
            # Combine relevant fields for embedding
            text_parts = []
            if "content" in chunk:
                text_parts.append(chunk["content"])
            if "filename" in chunk:
                text_parts.append(f"File: {chunk['filename']}")
            if "title" in chunk:
                text_parts.append(f"Title: {chunk['title']}")

            combined_text = " ".join(text_parts)
            texts.append(combined_text)

        # Compute embeddings
        self.embeddings = self.model.encode(texts, show_progress_bar=True)
        print(f"✅ Created embeddings with shape: {self.embeddings.shape}")

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """Search for similar chunks using vector similarity"""
        # Compute query embedding
        query_embedding = self.model.encode([query])

        # Compute cosine similarity
        similarities = np.dot(self.embeddings, query_embedding.T).flatten()

        # Get top results
        top_indices = np.argsort(similarities)[::-1][:num_results]

        # Return results with similarity scores
        results = []
        for idx in top_indices:
            result = self.chunks[idx].copy()
            result["similarity_score"] = float(similarities[idx])
            results.append(result)

        return results


def create_vector_index(
    chunks: List[Dict[str, Any]], model: SentenceTransformer
) -> VectorIndex:
    """Create a vector index from chunks using the specified model"""
    return VectorIndex(model, chunks)
