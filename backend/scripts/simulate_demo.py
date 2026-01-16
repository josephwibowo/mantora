#!/usr/bin/env python3
"""Live simulation of an agent interacting with the Mantora Proxy.

This script acts as an MCP client, connecting to the local proxy (via stdio)
and performing a sequence of actions to demonstrate:
1. Session creation
2. Warning detection (SELECT *)
3. Blocker modal (DELETE without WHERE)
4. Table casting

Usage:
    uv run python backend/scripts/simulate_demo.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


async def run_live_demo() -> None:
    print("🚀 Starting Live Demo Simulation...")

    # Path to the proxy script
    proxy_script = Path(__file__).parent / "run_proxy.py"
    config_path = Path(__file__).parent.parent.parent / "config.toml"

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "--project", "backend", "python", str(proxy_script), str(config_path)],
        env=None,
    )

    async with stdio_client(server_params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        # 1. Start Session
        print("\n[Client] Starting session 'Live Security Demo'...")
        result = await session.call_tool("session_start", arguments={"title": "Live Security Demo"})
        content = result.content[0]
        if isinstance(content, TextContent):
            session_id = content.text
            print(f"[Proxy] Session started: {session_id}")
        else:
            raise ValueError(f"Expected TextContent, got {type(content)}")

        # 2. Trigger Warning (SELECT *)
        print("\n[Client] Running broad query (should warn)...")
        try:
            # Using the 'query' tool (which the proxy forwards to mock-duckdb)
            await session.call_tool(
                "query", arguments={"sql": "SELECT * FROM sales_daily LIMIT 500"}
            )
            print("[Proxy] Query executed (check UI for 'NO_LIMIT' warning)")
        except Exception as e:
            print(f"[Proxy] Error: {e}")

        # 3. Trigger Blocker (DELETE without WHERE)
        print("\n[Client] Attempting dangerous DELETE (should BLOCK)...")
        print("👉 Go to the Mantora UI now! You should see the Blocker Modal.")
        try:
            await session.call_tool("query", arguments={"sql": "DELETE FROM users"})
            print("[Proxy] DELETE executed (User must have approved!)")
        except Exception as e:
            print(f"[Proxy] DELETE failed/blocked: {e}")

        # 4. Cast Table
        print("\n[Client] Casting generic table...")
        await session.call_tool(
            "cast_table",
            arguments={
                "title": "Demo Results",
                "sql": "SELECT 1 as id, 'test' as name",
                "rows": [{"id": 1, "name": "test"}],
            },
        )
        print("[Proxy] Table cast created.")

        print("\n✅ Simulation complete.")


if __name__ == "__main__":
    asyncio.run(run_live_demo())
