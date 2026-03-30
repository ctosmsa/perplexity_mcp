#!/usr/bin/env python3
"""
STDIO entry point for the Perplexity MCP Server.
Equivalent to src/index.ts
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from mcp.server.stdio import stdio_server

from .server import create_perplexity_server


def main() -> None:
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        print("Error: PERPLEXITY_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    async def run() -> None:
        server = create_perplexity_server("local-mcp")
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    try:
        asyncio.run(run())
    except Exception as e:
        print(f"Fatal error running server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
