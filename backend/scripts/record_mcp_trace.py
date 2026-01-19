#!/usr/bin/env python3
"""Record MCP tool schemas + deterministic tool call traces.

This script captures:
- `list_tools` output into `tools.json`
- A sequence of `call_tool` interactions into `traces/*.json`

The output is sanitized (emails/tokens/project IDs/timestamps/UUIDs) to prevent
accidentally committing sensitive values (PRI-NO-CREDENTIAL-MGMT, PIT-LOGGING-SENSITIVE).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, cast

# Add src to sys.path to allow running the script directly from any directory
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import jsonschema  # noqa: E402
from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402
from mcp.types import CallToolResult, Tool  # noqa: E402

from mantora.mcp.trace_sanitizer import sanitize_trace_payload  # noqa: E402


def _load_schema(project_root: Path) -> dict[str, Any]:
    schema_path = project_root / "tests" / "golden" / "schema.json"
    raw = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Golden schema must be a JSON object")
    return cast(dict[str, Any], raw)


def _validate_against_schema(*, schema: dict[str, Any], instance: dict[str, Any]) -> None:
    jsonschema.validate(instance=instance, schema=schema)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _slugify(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(ch if ch.isalnum() else "_")
    return "".join(out).strip("_")


def _load_playbook(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".json"}:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        try:
            import importlib

            yaml = importlib.import_module("yaml")
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "YAML playbook requested but PyYAML is not installed. "
                "Install it (e.g., `uv add --dev pyyaml`) or use a .json playbook."
            ) from e
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("Playbook must be a list of tool call entries")

    normalized: list[dict[str, Any]] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"Playbook entry {i} must be an object")
        tool_name = entry.get("tool_name") or entry.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            raise ValueError(f"Playbook entry {i} missing tool_name")
        arguments = entry.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ValueError(f"Playbook entry {i} arguments must be an object")
        normalized.append(
            {
                "id": entry.get("id") if isinstance(entry.get("id"), str) else None,
                "tool_name": tool_name,
                "arguments": arguments,
            }
        )
    return normalized


def _simplify_tool(tool: Tool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": tool.name,
        "inputSchema": tool.inputSchema,
    }
    if tool.description is not None:
        payload["description"] = tool.description
    if tool.outputSchema is not None:
        payload["outputSchema"] = tool.outputSchema
    return payload


def _simplify_call_tool_result(result: CallToolResult) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for block in result.content:
        if hasattr(block, "model_dump"):
            content.append(
                block.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude={"meta", "annotations"},
                )
            )
        else:  # pragma: no cover
            content.append({"type": getattr(block, "type", "unknown"), "text": str(block)})

    return {
        "content": content,
        "structuredContent": result.structuredContent,
        "isError": bool(result.isError),
    }


async def _record(
    *,
    command: list[str],
    target_type: str,
    output_dir: Path,
    playbook_path: Path | None,
) -> None:
    project_root = Path(__file__).parent.parent
    schema = _load_schema(project_root)

    out_root = output_dir / target_type
    traces_dir = out_root / "traces"

    params = StdioServerParameters(command=command[0], args=command[1:])
    async with stdio_client(params) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()

            list_tools_result = await session.list_tools()
            tools_payload = sanitize_trace_payload(
                {
                    "version": 1,
                    "target_type": target_type,
                    "tools": [_simplify_tool(t) for t in list_tools_result.tools],
                }
            )
            _validate_against_schema(schema=schema, instance=tools_payload)
            _write_json(out_root / "tools.json", tools_payload)

            if playbook_path is None:
                return

            playbook = _load_playbook(playbook_path)
            for idx, step in enumerate(playbook, start=1):
                tool_name = step["tool_name"]
                arguments = step["arguments"]

                call_result = await session.call_tool(tool_name, arguments)
                if not isinstance(call_result, CallToolResult):  # pragma: no cover
                    raise RuntimeError(f"Unexpected call_tool result type: {type(call_result)}")

                is_error = bool(call_result.isError)
                error_message: str | None = None
                if is_error and call_result.content:
                    first = call_result.content[0]
                    text = getattr(first, "text", None)
                    if isinstance(text, str) and text.strip():
                        error_message = text.strip()

                trace_payload = sanitize_trace_payload(
                    {
                        "version": 1,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": _simplify_call_tool_result(call_result),
                        "is_error": is_error,
                        "error_message": error_message,
                    }
                )
                _validate_against_schema(schema=schema, instance=trace_payload)

                base = step.get("id") or f"{idx:02d}_{_slugify(tool_name)}"
                _write_json(traces_dir / f"{base}.json", trace_payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--command",
        nargs="+",
        required=True,
        help="Target MCP server command (stdio). Example: --command python path/to/server.py",
    )
    parser.add_argument("--target-type", required=True, help="Target type (e.g., bigquery)")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent / "tests" / "golden"),
        help="Output base directory (default: backend/tests/golden)",
    )
    parser.add_argument(
        "--playbook",
        type=str,
        default=None,
        help="Playbook file (.yaml/.yml or .json). If omitted, only tools.json is recorded.",
    )

    args = parser.parse_args()
    asyncio.run(
        _record(
            command=args.command,
            target_type=args.target_type,
            output_dir=Path(args.output_dir),
            playbook_path=Path(args.playbook) if args.playbook else None,
        )
    )


if __name__ == "__main__":
    main()
