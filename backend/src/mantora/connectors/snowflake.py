"""Snowflake adapter for normalizing Snowflake MCP server tool calls.

Per PRI-NO-CREDENTIAL-MGMT: adapter extracts SQL/table evidence only (no DSNs).
Per PIT-ADAPTER-DRIFT: keep mappings conservative and allow unknown tools.

Reference: Snowflake MCP / Cortex Agents
Link: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp
Date: January 18, 2026
Protocol Version: 2025-06-18

Snowflake MCP Tool Types:
- CORTEX_SEARCH_SERVICE_QUERY: Cortex Search operations
- CORTEX_ANALYST_MESSAGE: Analyst queries (views only, not semantic models)
- SYSTEM_EXECUTE_SQL: SQL execution
- CORTEX_AGENT_RUN: Agent execution
- GENERIC: UDFs and stored procedures
"""

from __future__ import annotations

from typing import Any, ClassVar

from mantora.connectors.interface import BaseAdapter, StepCategory


class SnowflakeAdapter(BaseAdapter):
    """Adapter for Snowflake MCP servers."""

    _tool_categories: ClassVar[dict[str, StepCategory]] = {
        # Query execution
        "query": "query",
        "execute": "query",
        "run_query": "query",
        "snowflake_query": "query",
        "read_query": "query",
        "write_query": "query",
        # Schema inspection
        "describe": "schema",
        "describe_table": "schema",
        "get_schema": "schema",
        "table_schema": "schema",
        # List operations
        "list_tables": "list",
        "show_tables": "list",
        "tables": "list",
        "list_schemas": "list",
        "schemas": "list",
        "list_databases": "list",
        "databases": "list",
        "list_warehouses": "list",
        "warehouses": "list",
    }

    _tool_aliases: ClassVar[dict[str, str]] = {
        "sql": "query",
        "exec": "execute",
        "run": "execute",
        "desc": "describe",
    }

    @property
    def target_type(self) -> str:
        return "snowflake"

    def extract_evidence(
        self, tool_name: str, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        evidence = super().extract_evidence(tool_name, arguments, result)
        category = self.categorize_tool(tool_name)

        if category == "query":
            for key in ("sql", "query", "statement", "command"):
                if key in arguments and "sql" not in evidence:
                    evidence["sql"] = arguments[key]
                    break

        if category == "schema":
            for key in ("table", "table_name", "tableName", "name"):
                if key in arguments and "table" not in evidence:
                    evidence["table"] = arguments[key]
                    break

            for key in ("schema", "schema_name", "schemaName"):
                if key in arguments and "schema_name" not in evidence:
                    evidence["schema_name"] = arguments[key]
                    break

        if category == "list":
            lowered = tool_name.lower()
            if "database" in lowered:
                evidence["list_type"] = "databases"
            elif "schema" in lowered:
                evidence["list_type"] = "schemas"
            elif "warehouse" in lowered:
                evidence["list_type"] = "warehouses"
            else:
                evidence["list_type"] = "tables"

        return evidence
