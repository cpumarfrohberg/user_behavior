# Pydantic models for MongoDB Agent
"""Pydantic models for pydantic-ai-based MongoDB Agent system"""

from pydantic import BaseModel, Field

# Constants for validation bounds
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0
MIN_SCORE = 0.0
MAX_SCORE = 1.0
MIN_TOKEN_COUNT = 0


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


class SearchEntry(BaseModel):
    """Entry in the searches log tracking each search performed"""

    query: str = Field(..., description="The search query text")
    tags: list[str] = Field(default_factory=list, description="Tags used for filtering")
    num_results: int = Field(..., ge=0, description="Number of results returned")
    top_scores: list[float] = Field(
        default_factory=list, description="Top similarity scores from the search"
    )
    used_ids: list[str] = Field(
        default_factory=list, description="Source IDs actually used from this search"
    )
    eval: str = Field(
        ...,
        description="Evaluation string: 'relevant_count=X, top_scores=[a,b,c], decision=STOP|CONTINUE'",
    )


class SearchAnswer(BaseModel):
    """Structured response from search system"""

    answer: str = Field(..., description="The answer to the user's question")
    confidence: float = Field(
        ...,
        ge=MIN_CONFIDENCE,
        le=MAX_CONFIDENCE,
        description=f"Confidence in the answer ({MIN_CONFIDENCE} to {MAX_CONFIDENCE})",
    )
    sources_used: list[str] = Field(
        ..., description="List of source filenames used to generate the answer"
    )
    reasoning: str | None = Field(
        None, description="Brief explanation of the reasoning behind the answer"
    )
    searches: list[SearchEntry] = Field(
        ...,
        description="Log of searches performed with evaluation metadata. Must contain at least one entry.",
    )


class SearchAgentResult(BaseModel):
    """Result from MongoDB search agent query"""

    answer: SearchAnswer = Field(..., description="The answer from the agent")
    tool_calls: list[dict] = Field(
        ..., description="List of tool calls made during the query"
    )


class TokenUsage(BaseModel):
    """Token usage information from LLM API calls"""

    input_tokens: int = Field(
        ..., ge=MIN_TOKEN_COUNT, description="Number of input tokens used"
    )
    output_tokens: int = Field(
        ..., ge=MIN_TOKEN_COUNT, description="Number of output tokens used"
    )
    total_tokens: int = Field(..., ge=MIN_TOKEN_COUNT, description="Total tokens used")


class JudgeEvaluation(BaseModel):
    """Judge evaluation output for answer quality assessment"""

    overall_score: float = Field(
        ...,
        ge=MIN_SCORE,
        le=MAX_SCORE,
        description=f"Overall quality score ({MIN_SCORE} to {MAX_SCORE})",
    )
    accuracy: float = Field(
        ...,
        ge=MIN_SCORE,
        le=MAX_SCORE,
        description=f"Factual correctness score ({MIN_SCORE} to {MAX_SCORE})",
    )
    completeness: float = Field(
        ...,
        ge=MIN_SCORE,
        le=MAX_SCORE,
        description=f"Answer thoroughness score ({MIN_SCORE} to {MAX_SCORE})",
    )
    relevance: float = Field(
        ...,
        ge=MIN_SCORE,
        le=MAX_SCORE,
        description=f"Answer relevance to question ({MIN_SCORE} to {MAX_SCORE})",
    )
    reasoning: str = Field(..., description="Brief explanation of the evaluation")


class JudgeResult(BaseModel):
    """Result from judge evaluation including evaluation and usage"""

    evaluation: JudgeEvaluation = Field(..., description="Judge evaluation scores")
    usage: TokenUsage = Field(..., description="Token usage information")
