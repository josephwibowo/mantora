"""BigQuery adapter for normalizing BigQuery MCP server tool calls.

Per PRI-NO-CREDENTIAL-MGMT: adapter extracts SQL/table evidence only (no creds/DSNs).
Per PIT-ADAPTER-DRIFT: keep mappings conservative and allow unknown tools.

Reference: BigQuery MCP Tools Overview
Link: https://docs.cloud.google.com/bigquery/docs/reference/mcp/tools_overview
Date: January 18, 2026

Official BigQuery MCP tools:
- list_dataset_ids: List BigQuery dataset IDs in a Google Cloud project
- get_dataset_info: Get metadata information about a BigQuery dataset
- list_table_ids: List table IDs in a BigQuery dataset
- get_table_info: Get metadata information about a BigQuery table
- execute_sql: Run a SQL query (SELECT statements only)
"""

from __future__ import annotations

from typing import Any, ClassVar

from mantora.connectors.interface import BaseAdapter, StepCategory


class BigQueryAdapter(BaseAdapter):
    """Adapter for BigQuery MCP servers."""

    _tool_categories: ClassVar[dict[str, StepCategory]] = {
        # Official BigQuery MCP tools (per docs)
        "execute_sql": "query",
        "get_table_info": "schema",
        "list_table_ids": "list",
        "get_dataset_info": "schema",
        "list_dataset_ids": "list",
        # Common variants for compatibility
        "query": "query",
        "execute": "query",
        "run_query": "query",
        "bq_query": "query",
        "bigquery_query": "query",
        "jobs_query": "query",
        # Schema inspection variants
        "describe_table": "schema",
        "get_schema": "schema",
        "table_schema": "schema",
        # List operation variants
        "list_tables": "list",
        "tables": "list",
        "list_datasets": "list",
        "datasets": "list",
        "list_projects": "list",
        "projects": "list",
    }

    _tool_aliases: ClassVar[dict[str, str]] = {
        "sql": "execute_sql",
        "exec": "execute_sql",
        "run": "execute_sql",
        "query": "execute_sql",
    }

    @property
    def target_type(self) -> str:
        return "bigquery"

    def extract_evidence(
        self, tool_name: str, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        evidence = super().extract_evidence(tool_name, arguments, result)
        category = self.categorize_tool(tool_name)

        if category == "query":
            # execute_sql tool uses 'sql' or 'query' parameter
            for key in ("sql", "query", "statement"):
                if key in arguments and "sql" not in evidence:
                    evidence["sql"] = arguments[key]
                    break

        if category in ("schema", "list"):
            # BigQuery tools use project_id parameter
            for key in ("project", "project_id", "projectId"):
                if key in arguments and "project_id" not in evidence:
                    evidence["project_id"] = arguments[key]
                    break

            # Dataset parameter for dataset-related operations
            for key in ("dataset", "dataset_id", "datasetId"):
                if key in arguments and "dataset_id" not in evidence:
                    evidence["dataset_id"] = arguments[key]
                    break

        if category == "schema":
            # get_table_info and get_dataset_info tools
            for key in ("table", "table_name", "tableId", "table_id"):
                if key in arguments and "table" not in evidence:
                    evidence["table"] = arguments[key]
                    break

        if category == "list":
            # list_dataset_ids and list_table_ids tools
            lowered = tool_name.lower()
            if "dataset" in lowered and "table" not in lowered:
                evidence["list_type"] = "datasets"
            elif "table" in lowered:
                evidence["list_type"] = "tables"
            elif "project" in lowered:
                evidence["list_type"] = "projects"
            else:
                evidence["list_type"] = "unknown"

        return evidence
