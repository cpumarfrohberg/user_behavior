# Pydantic models for PydanticAI-based RAG system
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result with metadata for structured output"""

    content: str = Field(..., description="The content/text of the search result")
    filename: Optional[str] = Field(None, description="Filename or source identifier")
    title: Optional[str] = Field(None, description="Title of the document")
    similarity_score: Optional[float] = Field(
        None, description="Relevance score from search"
    )
    source: Optional[str] = Field(None, description="Source of the document")
    tags: Optional[List[str]] = Field(
        None, description="Tags associated with the document"
    )


class RAGAnswer(BaseModel):
    """Structured response from RAG system"""

    answer: str = Field(..., description="The answer to the user's question")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the answer (0.0 to 1.0)"
    )
    sources_used: List[str] = Field(
        ..., description="List of source filenames used to generate the answer"
    )
    reasoning: Optional[str] = Field(
        None, description="Brief explanation of the reasoning behind the answer"
    )
