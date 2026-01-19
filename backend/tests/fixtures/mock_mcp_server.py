"""Fixture-driven MCP server for golden trace replay.

Loads tool schemas from:
  backend/tests/golden/{target_type}/tools.json

Replays tool calls from:
  backend/tests/golden/{target_type}/traces/*.json

The replay is deterministic and argument-matched: each call_tool looks up a
recorded response based on (tool_name, arguments). If no match exists, the
server returns an MCP error result (isError=true).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server import Server


@dataclass(frozen=True)
class TraceEntry:
    tool_name: str
    arguments: dict[str, Any]
    result: types.CallToolResult
    is_error: bool
    error_message: str | None


def _repo_root() -> Path:
    # .../backend/tests/fixtures/mock_mcp_server.py -> repo root at parents[3]
    return Path(__file__).resolve().parents[3]


def _default_golden_root() -> Path:
    return _repo_root() / "backend" / "tests" / "golden"


def _load_tools(tools_path: Path) -> list[types.Tool]:
    payload = json.loads(tools_path.read_text(encoding="utf-8"))
    tools_raw = payload.get("tools")
    if not isinstance(tools_raw, list):
        raise ValueError(f"Invalid tools.json: missing tools list at {tools_path}")
    tools: list[types.Tool] = []
    for tool in tools_raw:
        if not isinstance(tool, dict):
            raise ValueError(f"Invalid tools.json tool entry: expected object, got {type(tool)}")
        tools.append(types.Tool.model_validate(tool))
    return tools


def _load_traces(traces_dir: Path) -> list[TraceEntry]:
    if not traces_dir.exists():
        return []
    entries: list[TraceEntry] = []
    for path in sorted(traces_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        tool_name = payload.get("tool_name")
        arguments = payload.get("arguments")
        result = payload.get("result")
        is_error = payload.get("is_error")
        error_message = payload.get("error_message")

        if not isinstance(tool_name, str):
            raise ValueError(f"{path}: tool_name must be a string")
        if not isinstance(arguments, dict):
            raise ValueError(f"{path}: arguments must be an object")
        if not isinstance(result, dict):
            raise ValueError(f"{path}: result must be an object")
        if not isinstance(is_error, bool):
            raise ValueError(f"{path}: is_error must be a boolean")
        if error_message is not None and not isinstance(error_message, str):
            raise ValueError(f"{path}: error_message must be string|null")

        entries.append(
            TraceEntry(
                tool_name=tool_name,
                arguments=arguments,
                result=types.CallToolResult.model_validate(result),
                is_error=is_error,
                error_message=error_message,
            )
        )
    return entries


def _args_key(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)


def create_mock_server(*, target_type: str, golden_root: Path | None = None) -> Server:
    golden_root = golden_root or _default_golden_root()
    target_root = golden_root / target_type
    tools_path = target_root / "tools.json"
    traces_dir = target_root / "traces"

    server = Server(f"mock-{target_type}")
    tools = _load_tools(tools_path)
    traces = _load_traces(traces_dir)
    trace_index: dict[tuple[str, str], TraceEntry] = {
        (t.tool_name, _args_key(t.arguments)): t for t in traces
    }

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        return tools

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
        arguments = arguments or {}
        key = (name, _args_key(arguments))
        expected = trace_index.get(key)
        if expected is None:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=(
                            "Replay mismatch: no recorded trace for tool call.\n"
                            f"Tool: {name}\n"
                            f"Arguments: {json.dumps(arguments, sort_keys=True)}\n"
                            f"Known traces: {len(traces)}"
                        ),
                    )
                ],
                isError=True,
            )

        if expected.is_error:
            return types.CallToolResult(
                content=expected.result.content,
                structuredContent=expected.result.structuredContent,
                isError=True,
            )

        return expected.result

    return server
