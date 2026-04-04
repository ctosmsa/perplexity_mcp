"""
Data types for the Perplexity MCP Server.
Equivalent to src/types.ts
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ChatMessage:
    content: str
    role: Optional[str] = None


@dataclass
class ChatChoice:
    message: ChatMessage
    finish_reason: Optional[str] = None
    index: Optional[int] = None


@dataclass
class TokenUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


@dataclass
class ChatCompletionResponse:
    choices: list[ChatChoice]
    citations: Optional[list[str]] = None
    usage: Optional[TokenUsage] = None
    id: Optional[str] = None
    model: Optional[str] = None
    created: Optional[int] = None


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: Optional[str] = None
    date: Optional[str] = None
    score: Optional[float] = None


@dataclass
class SearchUsage:
    tokens: Optional[int] = None


@dataclass
class SearchResponse:
    results: list[SearchResult]
    query: Optional[str] = None
    usage: Optional[SearchUsage] = None


@dataclass
class SearchRequestBody:
    query: str
    max_results: int
    max_tokens_per_page: int
    country: Optional[str] = None


@dataclass
class ChatCompletionOptions:
    search_recency_filter: Optional[str] = None   # "hour"|"day"|"week"|"month"|"year"
    search_domain_filter: Optional[list[str]] = None
    search_context_size: Optional[str] = None     # "low"|"medium"|"high"
    reasoning_effort: Optional[str] = None        # "minimal"|"low"|"medium"|"high"
