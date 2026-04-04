"""
Core MCP server implementation for the Perplexity API Platform.
Equivalent to src/server.ts
"""

import json
import os
import re
import asyncio
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.types import Tool, TextContent

from .types import Message, ChatCompletionResponse, SearchResponse, ChatCompletionOptions
from .validation import ChatCompletionResponseSchema, SearchResponseSchema
from .logger import logger

VERSION = "0.9.0"

PERPLEXITY_BASE_URL = os.environ.get("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")


# ---------------------------------------------------------------------------
# Proxy helpers
# ---------------------------------------------------------------------------

def get_proxy_url() -> Optional[str]:
    """Returns the first proxy URL found in the environment (priority order)."""
    return (
        os.environ.get("PERPLEXITY_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
    )


def build_http_client() -> httpx.AsyncClient:
    """Creates an httpx.AsyncClient with optional proxy support."""
    proxy_url = get_proxy_url()
    if proxy_url:
        return httpx.AsyncClient(proxy=proxy_url)
    return httpx.AsyncClient()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_messages(messages: Any, tool_name: str) -> list[Message]:
    """Validates and coerces raw message input.  Equivalent to validateMessages() in TS."""
    if not isinstance(messages, list):
        raise ValueError(f"Invalid arguments for {tool_name}: 'messages' must be an array")

    validated: list[Message] = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError(f"Invalid message at index {i}: must be an object")
        if not isinstance(msg.get("role"), str):
            raise ValueError(f"Invalid message at index {i}: 'role' must be a string")
        if not isinstance(msg.get("content"), str):
            raise ValueError(f"Invalid message at index {i}: 'content' must be a string")
        validated.append(Message(role=msg["role"], content=msg["content"]))

    return validated


def strip_thinking_tokens(content: str) -> str:
    """Removes <think>...</think> blocks from the response."""
    return re.sub(r"<think>[\s\S]*?</think>", "", content).strip()


# ---------------------------------------------------------------------------
# API request helpers
# ---------------------------------------------------------------------------

async def make_api_request(
    endpoint: str,
    body: dict,
    service_origin: Optional[str],
    stream: bool = False,
) -> httpx.Response:
    """Makes an authenticated POST request to the Perplexity API."""
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY environment variable is required")

    timeout_ms = int(os.environ.get("PERPLEXITY_TIMEOUT_MS", "300000"))
    timeout_s = timeout_ms / 1000.0

    url = f"{PERPLEXITY_BASE_URL}/{endpoint}"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": f"perplexity-mcp/{VERSION}",
        "X-Source": "pplx-mcp-server",
    }
    if service_origin:
        headers["X-Service"] = service_origin

    try:
        client = build_http_client()
        async with client:
            if stream:
                # For streaming responses we must not use the context-manager response
                request = client.build_request("POST", url, headers=headers, json=body)
                response = await client.send(request, stream=True)
            else:
                response = await client.post(
                    url, headers=headers, json=body, timeout=timeout_s
                )
    except httpx.TimeoutException:
        raise TimeoutError(
            f"Request timeout: Perplexity API did not respond within {timeout_ms}ms. "
            "Consider increasing PERPLEXITY_TIMEOUT_MS."
        )
    except Exception as e:
        raise RuntimeError(f"Network error while calling Perplexity API: {e}") from e

    if response.status_code >= 400:
        try:
            error_text = response.text
        except Exception:
            error_text = "Unable to parse error response"
        raise RuntimeError(
            f"Perplexity API error: {response.status_code} {response.reason_phrase}\n{error_text}"
        )

    return response


async def consume_sse_stream(response: httpx.Response) -> ChatCompletionResponseSchema:
    """Consumes a Server-Sent Events stream and assembles a ChatCompletionResponse."""
    content_parts: list[str] = []
    citations: Optional[list[str]] = None
    usage: Optional[dict] = None
    resp_id: Optional[str] = None
    resp_model: Optional[str] = None
    resp_created: Optional[int] = None
    buffer = ""

    async for raw_chunk in response.aiter_bytes():
        buffer += raw_chunk.decode("utf-8", errors="replace")
        lines = buffer.split("\n")
        buffer = lines.pop()  # keep potentially incomplete line

        for line in lines:
            trimmed = line.strip()
            if not trimmed or not trimmed.startswith("data:"):
                continue

            data = trimmed[len("data:"):].strip()
            if data == "[DONE]":
                continue

            try:
                parsed = json.loads(data)
                if parsed.get("id"):
                    resp_id = parsed["id"]
                if parsed.get("model"):
                    resp_model = parsed["model"]
                if parsed.get("created"):
                    resp_created = parsed["created"]
                if parsed.get("citations"):
                    citations = parsed["citations"]
                if parsed.get("usage"):
                    usage = parsed["usage"]

                delta = (parsed.get("choices") or [{}])[0].get("delta", {})
                if delta.get("content"):
                    content_parts.append(delta["content"])
            except json.JSONDecodeError:
                pass  # skip malformed keep-alive pings

    assembled = {
        "choices": [
            {
                "message": {"content": "".join(content_parts)},
                "finish_reason": "stop",
                "index": 0,
            }
        ],
        **({"citations": citations} if citations else {}),
        **({"usage": usage} if usage else {}),
        **({"id": resp_id} if resp_id else {}),
        **({"model": resp_model} if resp_model else {}),
        **({"created": resp_created} if resp_created else {}),
    }

    return ChatCompletionResponseSchema.model_validate(assembled)


async def perform_chat_completion(
    messages: list[Message],
    model: str = "sonar-pro",
    strip_thinking: bool = False,
    service_origin: Optional[str] = None,
    options: Optional[ChatCompletionOptions] = None,
) -> str:
    """Calls the Perplexity chat completions endpoint and returns the response text."""
    use_streaming = model == "sonar-deep-research"

    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }
    if use_streaming:
        body["stream"] = True
    if options:
        if options.search_recency_filter:
            body["search_recency_filter"] = options.search_recency_filter
        if options.search_domain_filter:
            body["search_domain_filter"] = options.search_domain_filter
        if options.search_context_size:
            body["web_search_options"] = {"search_context_size": options.search_context_size}
        if options.reasoning_effort:
            body["reasoning_effort"] = options.reasoning_effort

    response = await make_api_request("chat/completions", body, service_origin, stream=use_streaming)

    if use_streaming:
        data = await consume_sse_stream(response)
    else:
        try:
            raw_json = response.json()
            data = ChatCompletionResponseSchema.model_validate(raw_json)
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON response from Perplexity API: {e}") from e

    first_choice = data.choices[0]
    message_content: str = first_choice.message.content

    if strip_thinking:
        message_content = strip_thinking_tokens(message_content)

    if data.citations:
        message_content += "\n\nCitations:\n"
        for idx, citation in enumerate(data.citations, start=1):
            message_content += f"[{idx}] {citation}\n"

    return message_content


def format_search_results(data: SearchResponseSchema) -> str:
    """Formats search results into a human-readable string."""
    if not data.results:
        return "No search results found."

    lines = [f"Found {len(data.results)} search results:\n"]
    for idx, result in enumerate(data.results, start=1):
        lines.append(f"{idx}. **{result.title}**")
        lines.append(f"   URL: {result.url}")
        if result.snippet:
            lines.append(f"   {result.snippet}")
        if result.date:
            lines.append(f"   Date: {result.date}")
        lines.append("")

    return "\n".join(lines)


async def perform_search(
    query: str,
    max_results: int = 10,
    max_tokens_per_page: int = 1024,
    country: Optional[str] = None,
    service_origin: Optional[str] = None,
) -> str:
    """Calls the Perplexity Search API and returns formatted results."""
    body: dict[str, Any] = {
        "query": query,
        "max_results": max_results,
        "max_tokens_per_page": max_tokens_per_page,
    }
    if country:
        body["country"] = country

    response = await make_api_request("search", body, service_origin)

    try:
        raw_json = response.json()
        data = SearchResponseSchema.model_validate(raw_json)
    except Exception as e:
        raise RuntimeError(f"Failed to parse JSON response from Perplexity Search API: {e}") from e

    return format_search_results(data)


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------

def create_perplexity_server(service_origin: Optional[str] = None) -> Server:
    """
    Creates and configures the Perplexity MCP Server with all four tools.
    Equivalent to createPerplexityServer() in server.ts.
    """
    server = Server("ai.perplexity/mcp-server")

    # ------------------------------------------------------------------
    # list_tools
    # ------------------------------------------------------------------
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="perplexity_ask",
                description=(
                    "Answer a question using web-grounded AI (Sonar Pro model). "
                    "Best for: quick factual questions, summaries, explanations, and general Q&A. "
                    "Returns a text response with numbered citations. Fastest and cheapest option. "
                    "Supports filtering by recency (hour/day/week/month/year), domain restrictions, "
                    "and search context size. "
                    "For in-depth multi-source research, use perplexity_research instead. "
                    "For step-by-step reasoning and analysis, use perplexity_reason instead."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "Array of conversation messages",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                    "content": {"type": "string"},
                                },
                                "required": ["role", "content"],
                            },
                        },
                        "search_recency_filter": {
                            "type": "string",
                            "enum": ["hour", "day", "week", "month", "year"],
                            "description": "Filter search results by recency.",
                        },
                        "search_domain_filter": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Restrict search results to specific domains.",
                        },
                        "search_context_size": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Controls how much web context is retrieved.",
                        },
                    },
                    "required": ["messages"],
                },
            ),
            Tool(
                name="perplexity_research",
                description=(
                    "Conduct deep, multi-source research on a topic (Sonar Deep Research model). "
                    "Best for: literature reviews, comprehensive overviews, investigative queries "
                    "needing many sources. Returns a detailed response with numbered citations. "
                    "Significantly slower than other tools (30+ seconds). "
                    "For quick factual questions, use perplexity_ask instead. "
                    "For logical analysis and reasoning, use perplexity_reason instead."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "Array of conversation messages",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                    "content": {"type": "string"},
                                },
                                "required": ["role", "content"],
                            },
                        },
                        "strip_thinking": {
                            "type": "boolean",
                            "description": "If true, removes <think>...</think> tags from the response.",
                        },
                        "reasoning_effort": {
                            "type": "string",
                            "enum": ["minimal", "low", "medium", "high"],
                            "description": "Controls depth of deep research reasoning.",
                        },
                    },
                    "required": ["messages"],
                },
            ),
            Tool(
                name="perplexity_reason",
                description=(
                    "Analyze a question using step-by-step reasoning with web grounding "
                    "(Sonar Reasoning Pro model). "
                    "Best for: math, logic, comparisons, complex arguments, and tasks requiring "
                    "chain-of-thought. Returns a reasoned response with numbered citations. "
                    "Supports filtering by recency (hour/day/week/month/year), domain restrictions, "
                    "and search context size. "
                    "For quick factual questions, use perplexity_ask instead. "
                    "For comprehensive multi-source research, use perplexity_research instead."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "Array of conversation messages",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                    "content": {"type": "string"},
                                },
                                "required": ["role", "content"],
                            },
                        },
                        "strip_thinking": {
                            "type": "boolean",
                            "description": "If true, removes <think>...</think> tags from the response.",
                        },
                        "search_recency_filter": {
                            "type": "string",
                            "enum": ["hour", "day", "week", "month", "year"],
                        },
                        "search_domain_filter": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "search_context_size": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": ["messages"],
                },
            ),
            Tool(
                name="perplexity_search",
                description=(
                    "Search the web and return a ranked list of results with titles, URLs, "
                    "snippets, and dates. "
                    "Best for: finding specific URLs, checking recent news, verifying facts, "
                    "discovering sources. "
                    "Returns formatted results (title, URL, snippet, date) — no AI synthesis. "
                    "For AI-generated answers with citations, use perplexity_ask instead."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "description": "Maximum number of results to return (1-20, default: 10)",
                        },
                        "max_tokens_per_page": {
                            "type": "integer",
                            "minimum": 256,
                            "maximum": 2048,
                            "description": "Maximum tokens to extract per webpage (default: 1024)",
                        },
                        "country": {
                            "type": "string",
                            "description": "ISO 3166-1 alpha-2 country code for regional results",
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    # ------------------------------------------------------------------
    # call_tool dispatcher
    # ------------------------------------------------------------------
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "perplexity_ask":
            raw_messages = arguments.get("messages", [])
            messages = validate_messages(raw_messages, "perplexity_ask")
            options = ChatCompletionOptions(
                search_recency_filter=arguments.get("search_recency_filter"),
                search_domain_filter=arguments.get("search_domain_filter"),
                search_context_size=arguments.get("search_context_size"),
            )
            result = await perform_chat_completion(
                messages, "sonar-pro", False, service_origin,
                options if any([options.search_recency_filter, options.search_domain_filter, options.search_context_size]) else None,
            )
            return [TextContent(type="text", text=result)]

        elif name == "perplexity_research":
            raw_messages = arguments.get("messages", [])
            messages = validate_messages(raw_messages, "perplexity_research")
            strip = bool(arguments.get("strip_thinking", False))
            options = ChatCompletionOptions(
                reasoning_effort=arguments.get("reasoning_effort"),
            )
            result = await perform_chat_completion(
                messages, "sonar-deep-research", strip, service_origin,
                options if options.reasoning_effort else None,
            )
            return [TextContent(type="text", text=result)]

        elif name == "perplexity_reason":
            raw_messages = arguments.get("messages", [])
            messages = validate_messages(raw_messages, "perplexity_reason")
            strip = bool(arguments.get("strip_thinking", False))
            options = ChatCompletionOptions(
                search_recency_filter=arguments.get("search_recency_filter"),
                search_domain_filter=arguments.get("search_domain_filter"),
                search_context_size=arguments.get("search_context_size"),
            )
            result = await perform_chat_completion(
                messages, "sonar-reasoning-pro", strip, service_origin,
                options if any([options.search_recency_filter, options.search_domain_filter, options.search_context_size]) else None,
            )
            return [TextContent(type="text", text=result)]

        elif name == "perplexity_search":
            query = arguments["query"]
            max_results = int(arguments.get("max_results", 10))
            max_tokens_per_page = int(arguments.get("max_tokens_per_page", 1024))
            country = arguments.get("country")
            result = await perform_search(query, max_results, max_tokens_per_page, country, service_origin)
            return [TextContent(type="text", text=result)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    return server
