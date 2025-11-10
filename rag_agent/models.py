# Pydantic models for RAG Agent
"""Pydantic models for pydantic-ai-based RAG system"""

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result with metadata for structured output"""

    content: str = Field(..., description="The content/text of the search result")
    filename: str | None = Field(None, description="Filename or source identifier")
    title: str | None = Field(None, description="Title of the document")
    similarity_score: float | None = Field(
        None, description="Relevance score from search"
    )
    source: str | None = Field(None, description="Source of the document")
    tags: list[str] | None = Field(
        None, description="Tags associated with the document"
    )


class RAGAnswer(BaseModel):
    """Structured response from RAG system"""

    answer: str = Field(..., description="The answer to the user's question")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the answer (0.0 to 1.0)"
    )
    sources_used: list[str] = Field(
        ..., description="List of source filenames used to generate the answer"
    )
    reasoning: str | None = Field(
        None, description="Brief explanation of the reasoning behind the answer"
    )


class TokenUsage(BaseModel):
    """Token usage information from LLM API calls"""

    input_tokens: int = Field(..., ge=0, description="Number of input tokens used")
    output_tokens: int = Field(..., ge=0, description="Number of output tokens used")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")


class JudgeEvaluation(BaseModel):
    """Judge evaluation output for answer quality assessment"""

    overall_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall quality score (0.0 to 1.0)"
    )
    accuracy: float = Field(
        ..., ge=0.0, le=1.0, description="Factual correctness score (0.0 to 1.0)"
    )
    completeness: float = Field(
        ..., ge=0.0, le=1.0, description="Answer thoroughness score (0.0 to 1.0)"
    )
    relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Answer relevance to question (0.0 to 1.0)"
    )
    reasoning: str = Field(..., description="Brief explanation of the evaluation")


class JudgeResult(BaseModel):
    """Result from judge evaluation including evaluation and usage"""

    evaluation: JudgeEvaluation = Field(..., description="Judge evaluation scores")
    usage: TokenUsage = Field(..., description="Token usage information")
