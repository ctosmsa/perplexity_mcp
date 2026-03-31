"""
HTTP server entry point for the Perplexity MCP Server.
Equivalent to src/http.ts — uses FastAPI + SSE transport.
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.sse import SseServerTransport
import uvicorn

from perplexity_mcp.server import create_perplexity_server
from perplexity_mcp.logger import logger


def build_app() -> FastAPI:
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        logger.error("PERPLEXITY_API_KEY environment variable is missing. Requests will fail until set.")

    port = int(os.environ.get("PORT", "8080"))
    bind_address = os.environ.get("BIND_ADDRESS", "0.0.0.0")
    allowed_origins_raw = os.environ.get("ALLOWED_ORIGINS", "*")
    allowed_origins = allowed_origins_raw.split(",")

    app = FastAPI(title="Perplexity MCP Server")

    # CORS — mirror the TS behaviour: allow all origins if "*" is present
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    mcp_server = create_perplexity_server()
    sse_transport = SseServerTransport("/mcp/messages")

    @app.get("/mcp")
    async def mcp_sse(request: Request):
        """SSE endpoint — clients connect here to receive server-sent events."""
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0], streams[1], mcp_server.create_initialization_options()
            )

    @app.post("/mcp/messages")
    async def mcp_messages(request: Request):
        """Message endpoint — clients POST JSON-RPC messages here."""
        await sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "perplexity-mcp-server"}

    return app


app = build_app()

def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    bind_address = os.environ.get("BIND_ADDRESS", "0.0.0.0")

    logger.info(f"Perplexity MCP Server listening on http://{bind_address}:{port}/mcp")

    uvicorn.run(app, host=bind_address, port=port)


if __name__ == "__main__":
    main()
