from typing import Any

from mantora.mcp.tools import _infer_columns


def test_infer_columns_empty() -> None:
    assert _infer_columns([]) == []


def test_infer_columns_basic_types() -> None:
    rows = [{"id": 1, "name": "Alice", "active": True, "score": 95.5, "notes": None}]
    columns = _infer_columns(rows)

    assert len(columns) == 5

    schema_map = {col.name: col.type for col in columns}
    assert schema_map["id"] == "integer"
    assert schema_map["name"] == "string"
    assert schema_map["active"] == "boolean"
    assert schema_map["score"] == "float"
    assert schema_map["notes"] == "string"


def test_infer_columns_mixed_types_uses_first_row() -> None:
    # Only the first row is used for inference
    rows: list[dict[str, Any]] = [{"val": 10}, {"val": "string"}]
    columns = _infer_columns(rows)
    assert len(columns) == 1
    assert columns[0].name == "val"
    assert columns[0].type == "integer"


def test_infer_columns_null_handling() -> None:
    rows = [{"val": None}]
    columns = _infer_columns(rows)
    assert len(columns) == 1
    assert columns[0].name == "val"
    assert columns[0].type == "string"
