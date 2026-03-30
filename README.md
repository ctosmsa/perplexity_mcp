# Perplexity MCP Server — Python Port

Python conversion of the official
[perplexityai/modelcontextprotocol](https://github.com/perplexityai/modelcontextprotocol)
Node.js/TypeScript server.

## File mapping

| TypeScript (original) | Python (this port) | Notes |
|---|---|---|
| `src/types.ts` | `types.py` | Dataclasses replace TS interfaces |
| `src/validation.ts` | `validation.py` | Pydantic models replace Zod schemas |
| `src/logger.ts` | `logger.py` | Direct translation |
| `src/server.ts` | `server.py` | Core MCP tools + API logic |
| `src/index.ts` | `__main__.py` | STDIO entry point |
| `src/http.ts` | `http_server.py` | HTTP entry point (FastAPI + uvicorn) |

## Dependencies

| Node.js | Python |
|---|---|
| `@modelcontextprotocol/sdk` | `mcp` |
| `axios` / `undici` (fetch) | `httpx` |
| `zod` | `pydantic` |
| `express` + `cors` | `fastapi` + `CORSMiddleware` |
| Node.js built-ins | Python stdlib (`asyncio`, `re`, `json`, …) |

## Installation

```bash
pip install -e .
```

## Usage

### STDIO (for Claude Desktop, Cursor, VS Code…)

```bash
export PERPLEXITY_API_KEY=your_key_here
python -m perplexity_mcp
# or after pip install:
perplexity-mcp
```

Claude Desktop / Cursor `mcpServers` config:

```json
{
  "mcpServers": {
    "perplexity": {
      "command": "perplexity-mcp",
      "env": { "PERPLEXITY_API_KEY": "your_key_here" }
    }
  }
}
```

### HTTP server

```bash
export PERPLEXITY_API_KEY=your_key_here
python -m perplexity_mcp.http_server
# or after pip install:
perplexity-mcp-http
```

The server listens on `http://0.0.0.0:8080/mcp` by default.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `PERPLEXITY_API_KEY` | Perplexity API key **(required)** | — |
| `PERPLEXITY_BASE_URL` | Custom API base URL | `https://api.perplexity.ai` |
| `PERPLEXITY_TIMEOUT_MS` | Request timeout in ms | `300000` |
| `PERPLEXITY_PROXY` | Proxy URL | — |
| `HTTPS_PROXY` / `HTTP_PROXY` | Fallback proxy env vars | — |
| `PERPLEXITY_LOG_LEVEL` | `DEBUG\|INFO\|WARN\|ERROR` | `ERROR` |
| `PORT` | HTTP server port | `8080` |
| `BIND_ADDRESS` | HTTP bind address | `0.0.0.0` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `*` |

## Available tools

| Tool | Model | Description |
|---|---|---|
| `perplexity_ask` | `sonar-pro` | Quick Q&A with web grounding |
| `perplexity_research` | `sonar-deep-research` | Deep multi-source research (30s+) |
| `perplexity_reason` | `sonar-reasoning-pro` | Step-by-step reasoning + web |
| `perplexity_search` | Search API | Raw ranked URL results |
