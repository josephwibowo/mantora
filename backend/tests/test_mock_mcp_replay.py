from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _any_trace(target_type: str) -> dict[str, Any]:
    traces_dir = Path(__file__).parent / "golden" / target_type / "traces"
    trace_path = sorted(traces_dir.glob("*.json"))[0]
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("Trace fixture must be a JSON object")
    return payload


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["bigquery", "snowflake", "databricks"])
async def test_mock_mcp_server_replays_by_argument_match(target_type: str) -> None:
    trace = _any_trace(target_type)
    tool_name = trace["tool_name"]
    arguments = trace["arguments"]
    expected_is_error = bool(trace["is_error"])

    # When running via pre-commit or from root, we need to ensure the subprocess
    # runs from the backend directory so it can resolve 'tests.fixtures...'.
    backend_dir = Path(__file__).parent.parent

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", f"tests.fixtures.mock_{target_type}_server"],
        cwd=str(backend_dir),
    )
    async with stdio_client(params) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(tool_name, arguments)
            assert bool(result.isError) == expected_is_error


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["bigquery", "snowflake", "databricks"])
async def test_mock_mcp_server_returns_error_for_unknown_call(target_type: str) -> None:
    # When running via pre-commit or from root, we need to ensure the subprocess
    # runs from the backend directory so it can resolve 'tests.fixtures...'.
    backend_dir = Path(__file__).parent.parent

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", f"tests.fixtures.mock_{target_type}_server"],
        cwd=str(backend_dir),
    )
    async with stdio_client(params) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool("unknown_tool", {})
            assert result.isError is True
