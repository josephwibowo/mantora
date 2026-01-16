"""DuckDB adapter for normalizing DuckDB MCP server tool calls.

Per DEC-V0-CONNECTORS-DUCKDB-POSTGRES: v0 ships DuckDB + Postgres.
Per PIT-ADAPTER-DRIFT: use aliases to handle tool name variations.
"""

from __future__ import annotations

from typing import Any, ClassVar

from mantora.connectors.interface import BaseAdapter, StepCategory


class DuckDBAdapter(BaseAdapter):
    """Adapter for DuckDB MCP servers.

    Handles tool name variations and extracts DuckDB-specific evidence.
    """

    # Known DuckDB tool names and their categories
    _tool_categories: ClassVar[dict[str, StepCategory]] = {
        # Query execution
        "query": "query",
        "execute": "query",
        "run_query": "query",
        "duckdb_query": "query",
        "read_query": "query",
        # Schema inspection
        "describe": "schema",
        "describe_table": "schema",
        "get_schema": "schema",
        "table_schema": "schema",
        "duckdb_describe": "schema",
        # List operations
        "list_tables": "list",
        "show_tables": "list",
        "tables": "list",
        "list_databases": "list",
        "databases": "list",
    }

    # Aliases map alternative names to canonical names
    _tool_aliases: ClassVar[dict[str, str]] = {
        "exec": "execute",
        "sql": "query",
        "run": "execute",
        "desc": "describe",
        "schema": "describe_table",
    }

    @property
    def target_type(self) -> str:
        return "duckdb"

    def extract_evidence(
        self, tool_name: str, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract DuckDB-specific evidence from tool calls."""
        evidence = super().extract_evidence(tool_name, arguments, result)
        category = self.categorize_tool(tool_name)

        # For query tools, ensure we capture the SQL
        if category == "query":
            # DuckDB servers often use 'query' or 'sql' parameter
            for key in ("query", "sql", "statement", "command"):
                if key in arguments and "sql" not in evidence:
                    evidence["sql"] = arguments[key]
                    break

        # For schema tools, capture the table name
        if category == "schema":
            for key in ("table", "table_name", "tableName", "name"):
                if key in arguments and "table" not in evidence:
                    evidence["table"] = arguments[key]
                    break

        # For list tools, note what's being listed
        if category == "list":
            if "database" in tool_name.lower():
                evidence["list_type"] = "databases"
            else:
                evidence["list_type"] = "tables"

        return evidence
