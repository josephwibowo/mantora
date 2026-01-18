"""Connectors package - adapters for normalizing target MCP tool calls."""

from mantora.connectors.bigquery import BigQueryAdapter
from mantora.connectors.databricks import DatabricksAdapter
from mantora.connectors.duckdb import DuckDBAdapter
from mantora.connectors.interface import (
    DEFAULT_PREVIEW_CAP_BYTES,
    Adapter,
    BaseAdapter,
    NormalizedStep,
    StepCategory,
)
from mantora.connectors.postgres import PostgresAdapter
from mantora.connectors.registry import get_adapter, list_adapters, register_adapter
from mantora.connectors.snowflake import SnowflakeAdapter

__all__ = [
    "DEFAULT_PREVIEW_CAP_BYTES",
    "Adapter",
    "BaseAdapter",
    "BigQueryAdapter",
    "DatabricksAdapter",
    "DuckDBAdapter",
    "NormalizedStep",
    "PostgresAdapter",
    "SnowflakeAdapter",
    "StepCategory",
    "get_adapter",
    "list_adapters",
    "register_adapter",
]
