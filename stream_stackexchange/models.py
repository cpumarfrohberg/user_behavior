"""Pydantic models for StackExchange data"""

from pydantic import BaseModel, Field, field_validator


class User(BaseModel):
    """User/Owner information from StackExchange"""

    user_id: int | None = None
    display_name: str | None = None
    reputation: int | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, v):
        """Trim whitespace, handle None"""
        return v.strip() if v and isinstance(v, str) else None


class Comment(BaseModel):
    """Comment on a question or answer"""

    comment_id: int
    body: str
    score: int
    owner: User

    @field_validator("body", mode="before")
    @classmethod
    def normalize_body(cls, v):
        """Trim whitespace, ensure non-empty"""
        if v is None:
            return ""
        body = str(v).strip()
        return body if body else ""


class Answer(BaseModel):
    """Answer to a question"""

    answer_id: int
    body: str
    score: int
    is_accepted: bool
    owner: User | None = None
    comments: list[Comment] = Field(default_factory=list)

    @field_validator("body", mode="before")
    @classmethod
    def normalize_body(cls, v):
        """Trim whitespace"""
        return str(v).strip() if v else ""


class Question(BaseModel):
    """StackExchange question with answers and metadata"""

    question_id: int
    title: str
    body: str
    score: int
    tags: list[str] = Field(default_factory=list)
    site: str
    owner: User | None = None
    answers: list[Answer] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    collected_at: float

    @field_validator("title", "body", "site", mode="before")
    @classmethod
    def normalize_strings(cls, v):
        """Trim whitespace"""
        return str(v).strip() if v else ""

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v):
        """Remove empty tags, deduplicate"""
        if not v:
            return []
        tags = [str(t).strip() for t in v if t and str(t).strip()]
        return list(set(tags))  # Deduplicate
