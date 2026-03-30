"""
Validation schemas for the Perplexity MCP Server.
Equivalent to src/validation.ts (Zod → Pydantic).
"""

from typing import Optional
from pydantic import BaseModel, field_validator


class ChatMessageSchema(BaseModel):
    content: str
    role: Optional[str] = None


class ChatChoiceSchema(BaseModel):
    message: ChatMessageSchema
    finish_reason: Optional[str] = None
    index: Optional[int] = None


class TokenUsageSchema(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class ChatCompletionResponseSchema(BaseModel):
    choices: list[ChatChoiceSchema]
    citations: Optional[list[str]] = None
    usage: Optional[TokenUsageSchema] = None
    id: Optional[str] = None
    model: Optional[str] = None
    created: Optional[int] = None

    @field_validator("choices")
    @classmethod
    def choices_not_empty(cls, v: list) -> list:
        if len(v) < 1:
            raise ValueError("choices must have at least one element")
        return v


class SearchResultSchema(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    date: Optional[str] = None
    score: Optional[float] = None


class SearchUsageSchema(BaseModel):
    tokens: Optional[int] = None


class SearchResponseSchema(BaseModel):
    results: list[SearchResultSchema]
    query: Optional[str] = None
    usage: Optional[SearchUsageSchema] = None
