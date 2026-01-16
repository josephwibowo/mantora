"""Stub MCP server for integration testing.

A minimal MCP server that exposes a single tool for testing the proxy.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server


def create_stub_server() -> Server:
    """Create a stub MCP server with a simple echo tool."""
    server = Server("stub-server")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="echo",
                description="Echo back the input message",
                inputSchema={
                    "type": "object",
                    "properties": {"message": {"type": "string", "description": "Message to echo"}},
                    "required": ["message"],
                },
            ),
            types.Tool(
                name="add",
                description="Add two numbers",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"},
                    },
                    "required": ["a", "b"],
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        arguments = arguments or {}

        if name == "echo":
            message = arguments.get("message", "")
            return [types.TextContent(type="text", text=f"Echo: {message}")]

        if name == "add":
            a = arguments.get("a", 0)
            b = arguments.get("b", 0)
            return [types.TextContent(type="text", text=f"Result: {a + b}")]

        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def main() -> None:
    """Run the stub server."""
    server = create_stub_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
