"""Postgres adapter for normalizing Postgres MCP server tool calls.

Per DEC-V0-CONNECTORS-DUCKDB-POSTGRES: v0 ships DuckDB + Postgres.
Per PIT-ADAPTER-DRIFT: use aliases to handle tool name variations.
"""

from __future__ import annotations

from typing import Any, ClassVar

from mantora.connectors.interface import BaseAdapter, StepCategory


class PostgresAdapter(BaseAdapter):
    """Adapter for Postgres MCP servers.

    Handles tool name variations and extracts Postgres-specific evidence.
    """

    # Known Postgres tool names and their categories
    _tool_categories: ClassVar[dict[str, StepCategory]] = {
        # Query execution
        "query": "query",
        "execute": "query",
        "run_query": "query",
        "pg_query": "query",
        "postgres_query": "query",
        "read_query": "query",
        "write_query": "query",
        # Schema inspection
        "describe": "schema",
        "describe_table": "schema",
        "get_schema": "schema",
        "table_schema": "schema",
        "pg_describe": "schema",
        "get_table_info": "schema",
        # List operations
        "list_tables": "list",
        "show_tables": "list",
        "tables": "list",
        "list_schemas": "list",
        "schemas": "list",
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
        "pg_exec": "execute",
    }

    @property
    def target_type(self) -> str:
        return "postgres"

    def extract_evidence(
        self, tool_name: str, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract Postgres-specific evidence from tool calls."""
        evidence = super().extract_evidence(tool_name, arguments, result)
        category = self.categorize_tool(tool_name)

        # For query tools, ensure we capture the SQL
        if category == "query":
            for key in ("query", "sql", "statement", "command"):
                if key in arguments and "sql" not in evidence:
                    evidence["sql"] = arguments[key]
                    break

            # Postgres often has parameterized queries
            for key in ("params", "parameters", "args", "values"):
                if key in arguments:
                    evidence["params"] = arguments[key]
                    break

        # For schema tools, capture the table and schema name
        if category == "schema":
            for key in ("table", "table_name", "tableName", "name"):
                if key in arguments and "table" not in evidence:
                    evidence["table"] = arguments[key]
                    break

            # Postgres has schema namespaces
            for key in ("schema", "schema_name", "schemaName"):
                if key in arguments:
                    evidence["schema_name"] = arguments[key]
                    break

        # For list tools, note what's being listed
        if category == "list":
            if "database" in tool_name.lower():
                evidence["list_type"] = "databases"
            elif "schema" in tool_name.lower():
                evidence["list_type"] = "schemas"
            else:
                evidence["list_type"] = "tables"

        return evidence
