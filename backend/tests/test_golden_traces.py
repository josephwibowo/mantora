from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp import types

from mantora.connectors import get_adapter


def _schema() -> dict[str, Any]:
    path = Path(__file__).parent / "golden" / "schema.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("schema.json must be a JSON object")
    return payload


def _golden_roots() -> list[Path]:
    base = Path(__file__).parent / "golden"
    return [base / "bigquery", base / "snowflake", base / "databricks"]


def _iter_fixture_paths() -> list[Path]:
    paths: list[Path] = []
    for root in _golden_roots():
        paths.append(root / "tools.json")
        traces_dir = root / "traces"
        paths.extend(sorted(traces_dir.glob("*.json")))
    return paths


@pytest.mark.parametrize("fixture_path", _iter_fixture_paths())
def test_golden_fixture_files_validate_against_schema(fixture_path: Path) -> None:
    import importlib

    schema = _schema()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("Fixture must be a JSON object")
    jsonschema = importlib.import_module("jsonschema")
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.parametrize("fixture_path", _iter_fixture_paths())
def test_golden_fixture_files_are_deterministic_json(fixture_path: Path) -> None:
    # Ensure files are stable and parseable without trailing junk.
    contents = fixture_path.read_text(encoding="utf-8")
    parsed = json.loads(contents)
    assert parsed is not None


@pytest.mark.parametrize("target_type", ["bigquery", "snowflake", "databricks"])
def test_golden_traces_normalize_as_expected(target_type: str) -> None:
    adapter = get_adapter(target_type)
    traces_dir = Path(__file__).parent / "golden" / target_type / "traces"

    for trace_path in sorted(traces_dir.glob("*.json")):
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Trace fixture must be a JSON object")
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
        assert normalized.status == ("error" if is_error else "ok")

        expected_evidence = expected.get("evidence")
        if isinstance(expected_evidence, dict):
            for key, value in expected_evidence.items():
                assert normalized.evidence.get(key) == value
