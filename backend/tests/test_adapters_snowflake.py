from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp import types

from mantora.connectors import SnowflakeAdapter


def _golden_dir() -> Path:
    return Path(__file__).parent / "golden" / "snowflake" / "traces"


def _iter_trace_paths() -> list[Path]:
    return sorted(_golden_dir().glob("*.json"))


@pytest.mark.parametrize("trace_path", _iter_trace_paths())
def test_snowflake_adapter_normalizes_golden_traces(trace_path: Path) -> None:
    adapter = SnowflakeAdapter()
    payload: dict[str, Any] = json.loads(trace_path.read_text(encoding="utf-8"))
    expected = payload.get("expected")
    assert isinstance(expected, dict)

    tool_name = payload["tool_name"]
    arguments = payload["arguments"]
    result = types.CallToolResult.model_validate(payload["result"])
    is_error = bool(payload["is_error"])
    error_message = payload.get("error_message")

    normalized = adapter.normalize(
        tool_name,
        arguments,
        result,
        is_error=is_error,
        error_message=error_message,
    )

    assert normalized.category == expected["category"]
    if is_error:
        assert normalized.status == "error"
    else:
        assert normalized.status == "ok"

    expected_evidence = expected.get("evidence")
    if isinstance(expected_evidence, dict):
        for key, value in expected_evidence.items():
            assert normalized.evidence.get(key) == value


def test_snowflake_adapter_categorizes_core_tools() -> None:
    adapter = SnowflakeAdapter()
    assert adapter.categorize_tool("query") == "query"
    assert adapter.categorize_tool("describe_table") == "schema"
    assert adapter.categorize_tool("list_tables") == "list"
    assert adapter.categorize_tool("list_schemas") == "list"
    assert adapter.categorize_tool("list_databases") == "list"
