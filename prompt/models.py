# Pydantic models for structured RAG output
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result with metadata"""

    content: str = Field(..., description="The actual content/text of the document")
    filename: str = Field(..., description="Source filename")
    title: Optional[str] = Field(None, description="Document title if available")
    similarity_score: Optional[float] = Field(
        None, description="Similarity score for vector search"
    )


class RAGAnswer(BaseModel):
    """Structured answer from RAG system"""

    answer: str = Field(..., description="The answer to the user's question")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the answer (0.0 to 1.0)"
    )
    sources_used: List[str] = Field(
        ..., description="List of filenames used as sources"
    )
    reasoning: Optional[str] = Field(
        None, description="Brief explanation of the reasoning behind the answer"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
