"""Databricks SQL adapter for normalizing Databricks MCP server tool calls.

Per PRI-NO-CREDENTIAL-MGMT: adapter extracts SQL/table evidence only (no creds/DSNs).
Per PIT-ADAPTER-DRIFT: keep mappings conservative and allow unknown tools.

Reference: Databricks Model Context Protocol (MCP)
Link: https://docs.databricks.com/aws/en/generative-ai/mcp/
Date: January 18, 2026

Databricks MCP Options:
- Managed MCP servers: Vector Search, Unity Catalog functions, Genie Spaces, DBSQL
- External MCP servers: Third-party APIs, external services
- Custom MCP servers: User-defined implementations
Security: Unity Catalog permissions enforced for managed MCP
"""

from __future__ import annotations

from typing import Any, ClassVar

from mantora.connectors.interface import BaseAdapter, StepCategory


class DatabricksAdapter(BaseAdapter):
    """Adapter for Databricks SQL MCP servers."""

    _tool_categories: ClassVar[dict[str, StepCategory]] = {
        # Query execution
        "query": "query",
        "execute": "query",
        "run_query": "query",
        "databricks_query": "query",
        "statement": "query",
        # Schema inspection
        "describe_table": "schema",
        "get_schema": "schema",
        "table_schema": "schema",
        # List operations
        "list_tables": "list",
        "tables": "list",
        "list_schemas": "list",
        "schemas": "list",
        "list_catalogs": "list",
        "catalogs": "list",
    }

    _tool_aliases: ClassVar[dict[str, str]] = {
        "sql": "query",
        "exec": "execute",
        "run": "execute",
        "desc": "describe_table",
    }

    @property
    def target_type(self) -> str:
        return "databricks"

    def extract_evidence(
        self, tool_name: str, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        evidence = super().extract_evidence(tool_name, arguments, result)
        category = self.categorize_tool(tool_name)

        if category == "query":
            for key in ("sql", "query", "statement"):
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

            for key in ("catalog", "catalog_name", "catalogName"):
                if key in arguments and "catalog_name" not in evidence:
                    evidence["catalog_name"] = arguments[key]
                    break

        if category == "list":
            lowered = tool_name.lower()
            if "catalog" in lowered:
                evidence["list_type"] = "catalogs"
            elif "schema" in lowered:
                evidence["list_type"] = "schemas"
            else:
                evidence["list_type"] = "tables"

        return evidence
