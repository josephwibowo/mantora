"""Mock Snowflake MCP server backed by golden fixtures."""

from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server

from tests.fixtures.mock_mcp_server import create_mock_server


def create_mock_snowflake_server() -> Server:
    return create_mock_server(target_type="snowflake")


async def main() -> None:
    server = create_mock_snowflake_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
