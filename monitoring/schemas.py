"""Pydantic schemas for data validation and response models."""

from typing import Any

from pydantic import BaseModel


# Input models (for validation before database operations)
class LogCreate(BaseModel):
    agent_name: str | None = None
    provider: str | None = None
    model: str | None = None
    user_prompt: str | None = None
    instructions: str | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    assistant_answer: str | None = None
    raw_json: str | None = None
    input_cost: float | None = None
    output_cost: float | None = None
    total_cost: float | None = None


class EvalCheckCreate(BaseModel):
    log_id: int
    check_name: str
    passed: bool | None = None
    score: float | None = None
    details: str | None = None


class GuardrailEventCreate(BaseModel):
    log_id: int
    guardrail_name: str
    triggered: bool
    reason: str | None = None


# Response models (for data returned from database)
class EvalCheckResponse(BaseModel):
    check_name: str
    passed: bool | None
    score: float | None
    details: str | None


class GuardrailEventResponse(BaseModel):
    guardrail_name: str
    triggered: bool
    reason: str | None


class LogResponse(BaseModel):
    id: int
    created_at: Any
    agent_name: str | None
    provider: str | None
    model: str | None
    user_prompt: str | None
    instructions: str | None
    assistant_answer: str | None
    total_input_tokens: int | None
    total_output_tokens: int | None
    input_cost: float | None
    output_cost: float | None
    total_cost: float | None
    checks: list[EvalCheckResponse]
    guardrail_events: list[GuardrailEventResponse]


class LogSummaryResponse(BaseModel):
    id: int
    created_at: Any
    agent_name: str | None
    model: str | None
    user_prompt: str | None
    total_cost: float | None
    total_input_tokens: int | None
    total_output_tokens: int | None
