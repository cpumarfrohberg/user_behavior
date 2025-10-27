# Simple chunking utilities - your approach
from typing import Any, Dict, List


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Simple text chunking - your approach"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def chunk_documents(
    documents: List[Dict[str, Any]], chunk_size: int = 1000, overlap: int = 200
) -> List[Dict[str, Any]]:
    """Chunk documents using simple approach"""
    chunks = []

    for doc in documents:
        content = doc.get("content", "")
        text_chunks = chunk_text(content, chunk_size, overlap)

        for i, chunk_content in enumerate(text_chunks):
            chunk = {
                "content": chunk_content,
                "title": doc.get("title", "Untitled"),
                "source": doc.get("source", "Unknown"),
                "chunk_index": i,
            }
            chunks.append(chunk)

    return chunks
