"""Tests for target adapters."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mantora.connectors import (
    DuckDBAdapter,
    NormalizedStep,
    PostgresAdapter,
    get_adapter,
    list_adapters,
)
from mantora.connectors.interface import DEFAULT_PREVIEW_CAP_BYTES
from mantora.connectors.registry import GenericAdapter

# --- Adapter Registry Tests ---


def test_get_adapter_duckdb() -> None:
    """Registry returns DuckDB adapter for 'duckdb' type."""
    adapter = get_adapter("duckdb")
    assert isinstance(adapter, DuckDBAdapter)
    assert adapter.target_type == "duckdb"


def test_get_adapter_postgres() -> None:
    """Registry returns Postgres adapter for 'postgres' type."""
    adapter = get_adapter("postgres")
    assert isinstance(adapter, PostgresAdapter)
    assert adapter.target_type == "postgres"


def test_get_adapter_postgres_aliases() -> None:
    """Registry handles postgres aliases."""
    for alias in ("postgresql", "pg"):
        adapter = get_adapter(alias)
        assert isinstance(adapter, PostgresAdapter)


def test_get_adapter_unknown_returns_generic() -> None:
    """Registry returns generic adapter for unknown types."""
    adapter = get_adapter("unknown_db")
    assert isinstance(adapter, GenericAdapter)


def test_get_adapter_case_insensitive() -> None:
    """Registry handles case variations."""
    adapter = get_adapter("DuckDB")
    assert isinstance(adapter, DuckDBAdapter)


def test_list_adapters() -> None:
    """List adapters returns known types."""
    adapters = list_adapters()
    assert "duckdb" in adapters
    assert "postgres" in adapters
    assert "generic" in adapters


# --- DuckDB Adapter Tests ---


class TestDuckDBAdapter:
    """Tests for DuckDB adapter."""

    @pytest.fixture
    def adapter(self) -> DuckDBAdapter:
        return DuckDBAdapter()

    def test_categorize_query_tools(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter categorizes query tools correctly."""
        for tool in ("query", "execute", "run_query", "duckdb_query"):
            assert adapter.categorize_tool(tool) == "query"

    def test_categorize_schema_tools(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter categorizes schema tools correctly."""
        for tool in ("describe", "describe_table", "get_schema"):
            assert adapter.categorize_tool(tool) == "schema"

    def test_categorize_list_tools(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter categorizes list tools correctly."""
        for tool in ("list_tables", "show_tables", "tables"):
            assert adapter.categorize_tool(tool) == "list"

    def test_categorize_unknown_tool(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter returns 'unknown' for unrecognized tools."""
        assert adapter.categorize_tool("some_random_tool") == "unknown"

    def test_tool_aliases(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter resolves tool aliases."""
        # 'sql' is an alias for 'query'
        assert adapter.categorize_tool("sql") == "query"
        # 'desc' is an alias for 'describe'
        assert adapter.categorize_tool("desc") == "schema"

    def test_extract_evidence_query(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter extracts SQL from query tools."""
        evidence = adapter.extract_evidence("query", {"sql": "SELECT * FROM users"}, None)
        assert evidence["sql"] == "SELECT * FROM users"

    def test_extract_evidence_query_alternate_key(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter handles alternate SQL parameter names."""
        evidence = adapter.extract_evidence("query", {"query": "SELECT 1"}, None)
        assert evidence["sql"] == "SELECT 1"

    def test_extract_evidence_schema(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter extracts table name from schema tools."""
        evidence = adapter.extract_evidence("describe_table", {"table": "users"}, None)
        assert evidence["table"] == "users"

    def test_extract_evidence_list(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter notes list type."""
        evidence = adapter.extract_evidence("list_tables", {}, None)
        assert evidence["list_type"] == "tables"

        evidence = adapter.extract_evidence("list_databases", {}, None)
        assert evidence["list_type"] == "databases"

    def test_normalize_query(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter normalizes query tool calls."""
        result = adapter.normalize(
            "query",
            {"sql": "SELECT * FROM users"},
            '{"rows": [[1, "alice"]]}',
        )

        assert isinstance(result, NormalizedStep)
        assert result.category == "query"
        assert result.tool_name == "query"
        assert result.status == "ok"
        assert result.evidence["sql"] == "SELECT * FROM users"
        assert "rows" in result.preview_text

    def test_normalize_error(self, adapter: DuckDBAdapter) -> None:
        """DuckDB adapter normalizes error responses."""
        result = adapter.normalize(
            "query",
            {"sql": "INVALID SQL"},
            None,
            is_error=True,
            error_message="Syntax error",
        )

        assert result.status == "error"
        assert result.error_message == "Syntax error"


# --- Postgres Adapter Tests ---


class TestPostgresAdapter:
    """Tests for Postgres adapter."""

    @pytest.fixture
    def adapter(self) -> PostgresAdapter:
        return PostgresAdapter()

    def test_categorize_query_tools(self, adapter: PostgresAdapter) -> None:
        """Postgres adapter categorizes query tools correctly."""
        for tool in ("query", "execute", "pg_query", "postgres_query"):
            assert adapter.categorize_tool(tool) == "query"

    def test_categorize_schema_tools(self, adapter: PostgresAdapter) -> None:
        """Postgres adapter categorizes schema tools correctly."""
        for tool in ("describe", "describe_table", "get_table_info"):
            assert adapter.categorize_tool(tool) == "schema"

    def test_categorize_list_tools(self, adapter: PostgresAdapter) -> None:
        """Postgres adapter categorizes list tools correctly."""
        for tool in ("list_tables", "list_schemas", "list_databases"):
            assert adapter.categorize_tool(tool) == "list"

    def test_extract_evidence_with_params(self, adapter: PostgresAdapter) -> None:
        """Postgres adapter extracts query parameters."""
        evidence = adapter.extract_evidence(
            "pg_query",
            {"query": "SELECT * FROM users WHERE id = $1", "params": [42]},
            None,
        )
        assert evidence["sql"] == "SELECT * FROM users WHERE id = $1"
        assert evidence["params"] == [42]

    def test_extract_evidence_schema_namespace(self, adapter: PostgresAdapter) -> None:
        """Postgres adapter extracts schema namespace."""
        evidence = adapter.extract_evidence(
            "describe_table",
            {"table_name": "users", "schema_name": "public"},
            None,
        )
        assert evidence["table"] == "users"
        assert evidence["schema_name"] == "public"

    def test_extract_evidence_list_types(self, adapter: PostgresAdapter) -> None:
        """Postgres adapter notes different list types."""
        assert adapter.extract_evidence("list_tables", {}, None)["list_type"] == "tables"
        assert adapter.extract_evidence("list_schemas", {}, None)["list_type"] == "schemas"
        assert adapter.extract_evidence("list_databases", {}, None)["list_type"] == "databases"


# --- Preview Capping Tests ---


class TestPreviewCapping:
    """Tests for preview payload capping (PRI-HARD-CAPS-ALWAYS)."""

    @pytest.fixture
    def adapter(self) -> DuckDBAdapter:
        return DuckDBAdapter()

    def test_preview_not_truncated_small_result(self, adapter: DuckDBAdapter) -> None:
        """Small results are not truncated."""
        result = adapter.normalize("query", {"sql": "SELECT 1"}, "small result")

        assert result.preview_text == "small result"
        assert result.preview_truncated is False

    def test_preview_truncated_large_result(self, adapter: DuckDBAdapter) -> None:
        """Large results are truncated."""
        large_result = "x" * (DEFAULT_PREVIEW_CAP_BYTES + 1000)
        result = adapter.normalize("query", {"sql": "SELECT 1"}, large_result)

        assert len(result.preview_text.encode("utf-8")) <= DEFAULT_PREVIEW_CAP_BYTES
        assert result.preview_truncated is True

    def test_preview_custom_cap(self, adapter: DuckDBAdapter) -> None:
        """Custom preview cap is respected."""
        result = adapter.normalize(
            "query",
            {"sql": "SELECT 1"},
            "x" * 1000,
            max_preview_bytes=100,
        )

        assert len(result.preview_text.encode("utf-8")) <= 100
        assert result.preview_truncated is True

    def test_preview_handles_dict_result(self, adapter: DuckDBAdapter) -> None:
        """Preview handles dict results."""
        dict_result = {"rows": [[1, 2], [3, 4]], "count": 2}
        result = adapter.normalize("query", {"sql": "SELECT 1"}, dict_result)

        # Should be JSON formatted
        assert "rows" in result.preview_text
        assert result.preview_truncated is False

    def test_preview_handles_none_result(self, adapter: DuckDBAdapter) -> None:
        """Preview handles None results."""
        result = adapter.normalize("query", {"sql": "SELECT 1"}, None)

        assert result.preview_text == ""
        assert result.preview_truncated is False


# --- Mock MCP Result Tests ---


@dataclass
class MockContent:
    """Mock MCP content."""

    type: str
    text: str


@dataclass
class MockCallToolResult:
    """Mock MCP CallToolResult."""

    content: list[MockContent]


class TestMCPResultHandling:
    """Tests for handling MCP CallToolResult objects."""

    @pytest.fixture
    def adapter(self) -> DuckDBAdapter:
        return DuckDBAdapter()

    def test_preview_extracts_mcp_content(self, adapter: DuckDBAdapter) -> None:
        """Preview extracts text from MCP CallToolResult."""
        mcp_result = MockCallToolResult(
            content=[MockContent(type="text", text='{"rows": [[1, 2]]}')]
        )
        result = adapter.normalize("query", {"sql": "SELECT 1"}, mcp_result)

        assert '{"rows": [[1, 2]]}' in result.preview_text

    def test_preview_handles_empty_mcp_content(self, adapter: DuckDBAdapter) -> None:
        """Preview handles empty MCP content."""
        mcp_result = MockCallToolResult(content=[])
        result = adapter.normalize("query", {"sql": "SELECT 1"}, mcp_result)

        # Falls back to string representation
        assert result.preview_text != ""
