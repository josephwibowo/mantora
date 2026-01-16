"""Mock DuckDB MCP server for deterministic demo.

Exposes DuckDB-like tools with stable, ordered responses for demo playbook.
All data is deterministic with fixed seeds and ordering.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Deterministic sales data for demo
# Deterministic sales data for demo (generated)
# Deterministic sales data for demo (generated)
SALES_DATA: list[dict[str, Any]] = []
regions = ["East", "West", "North", "South", "Europe", "Asia"]
base_revenue = 10000.00
import math  # noqa: E402

# Generate 500 rows of data
for i in range(500):
    day_offset = i % 50
    region_idx = i % len(regions)

    day = f"2026-01-{day_offset + 1:02d}" if day_offset < 31 else f"2026-02-{day_offset - 30:02d}"
    region = regions[region_idx]

    # Deterministic "random" revenue
    revenue = base_revenue + (math.sin(i) * 5000) + (region_idx * 1000)
    revenue = round(revenue, 2)

    SALES_DATA.append({"day": day, "region": region, "revenue": revenue})


def query_sales(sql: str) -> dict[str, Any]:
    """Execute a query against sales_daily data."""
    sql_upper = sql.upper()

    # Handle the demo playbook query: last 14 days
    if "WHERE day >= DATE '2025-12-29'" in sql_upper and "LIMIT 200" in sql_upper:
        rows = [[row["day"], row["region"], row["revenue"]] for row in SALES_DATA]
        return {
            "columns": ["day", "region", "revenue"],
            "rows": rows,
            "row_count": len(rows),
        }

    # Handle the aggregation query: last 7d vs prior 7d
    if "LAST_7D" in sql_upper and "PRIOR_7D" in sql_upper:
        # Compute aggregates
        regions = {}
        for row in SALES_DATA:
            region = str(row["region"])
            day = str(row["day"])
            revenue = float(row["revenue"])

            if region not in regions:
                regions[region] = {"last_7d": 0.0, "prior_7d": 0.0}

            if day >= "2026-01-05":
                regions[region]["last_7d"] += revenue
            else:
                regions[region]["prior_7d"] += revenue

        # Build result rows
        result_rows: list[list[str | float]] = []
        for region, totals in regions.items():
            delta = totals["last_7d"] - totals["prior_7d"]
            result_rows.append([region, totals["last_7d"], totals["prior_7d"], delta])

        # Sort by delta ascending (biggest decline first)
        result_rows.sort(key=lambda x: x[3])

        return {
            "columns": ["region", "last_7d", "prior_7d", "delta"],
            "rows": result_rows,
            "row_count": len(result_rows),
        }

    # Generic SELECT fallback
    if "SELECT" in sql_upper:
        return {
            "columns": ["id", "name", "value"],
            "rows": [
                [1, "alpha", 100],
                [2, "beta", 200],
                [3, "gamma", 300],
            ],
            "row_count": 3,
        }

    # Non-SELECT queries
    return {"affected_rows": 1}


def create_mock_duckdb_server() -> Server:
    """Create a mock DuckDB MCP server with deterministic sales data."""
    server = Server("mock-duckdb")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="query",
                description="Execute a SQL query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SQL query to execute"},
                    },
                    "required": ["sql"],
                },
            ),
            types.Tool(
                name="list_tables",
                description="List all tables in the database",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="describe_table",
                description="Get schema information for a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Table name"},
                    },
                    "required": ["table"],
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        arguments = arguments or {}

        if name == "query":
            sql = arguments.get("sql", "")
            result = query_sales(sql)
            return [types.TextContent(type="text", text=json.dumps(result))]

        if name == "list_tables":
            tables = ["users", "orders", "products", "sales_daily"]
            return [types.TextContent(type="text", text=json.dumps({"tables": tables}))]

        if name == "describe_table":
            table = arguments.get("table", "unknown")

            if table == "sales_daily":
                schema = {
                    "table": "sales_daily",
                    "columns": [
                        {"name": "day", "type": "DATE", "nullable": False},
                        {"name": "region", "type": "VARCHAR", "nullable": False},
                        {"name": "revenue", "type": "DECIMAL(10,2)", "nullable": False},
                    ],
                }
            else:
                schema = {
                    "table": table,
                    "columns": [
                        {"name": "id", "type": "INTEGER", "nullable": False},
                        {"name": "name", "type": "VARCHAR", "nullable": True},
                        {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                    ],
                }

            return [types.TextContent(type="text", text=json.dumps(schema))]

        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def main() -> None:
    """Run the mock DuckDB server."""
    server = create_mock_duckdb_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
