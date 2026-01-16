"""Mock Postgres MCP server for testing adapters.

Exposes a minimal set of Postgres-like tools with deterministic responses.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server


def create_mock_postgres_server() -> Server:
    """Create a mock Postgres MCP server."""
    server = Server("mock-postgres")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="pg_query",
                description="Execute a SQL query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL query to execute"},
                        "params": {
                            "type": "array",
                            "description": "Query parameters",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="list_tables",
                description="List all tables in a schema",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema": {
                            "type": "string",
                            "description": "Schema name",
                            "default": "public",
                        },
                    },
                },
            ),
            types.Tool(
                name="describe_table",
                description="Get schema information for a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table name"},
                        "schema_name": {
                            "type": "string",
                            "description": "Schema name",
                            "default": "public",
                        },
                    },
                    "required": ["table_name"],
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        arguments = arguments or {}

        if name == "pg_query":
            query = arguments.get("query", "")
            params = arguments.get("params", [])
            # Return mock query results
            if "SELECT" in query.upper():
                result = {
                    "columns": ["id", "email", "active"],
                    "rows": [
                        [1, "alice@example.com", True],
                        [2, "bob@example.com", False],
                    ],
                    "row_count": 2,
                    "params_used": len(params),
                }
                return [types.TextContent(type="text", text=json.dumps(result))]
            # For non-SELECT queries
            return [types.TextContent(type="text", text='{"affected_rows": 1}')]

        if name == "list_tables":
            schema = arguments.get("schema", "public")
            tables = ["accounts", "transactions", "audit_log"]
            return [
                types.TextContent(
                    type="text", text=json.dumps({"schema": schema, "tables": tables})
                )
            ]

        if name == "describe_table":
            table = arguments.get("table_name", "unknown")
            schema = arguments.get("schema_name", "public")
            result = {
                "table": table,
                "schema": schema,
                "columns": [
                    {"name": "id", "type": "serial", "nullable": False, "primary_key": True},
                    {"name": "email", "type": "varchar(255)", "nullable": False},
                    {"name": "active", "type": "boolean", "nullable": False, "default": "true"},
                ],
            }
            return [types.TextContent(type="text", text=json.dumps(result))]

        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def main() -> None:
    """Run the mock Postgres server."""
    server = create_mock_postgres_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
