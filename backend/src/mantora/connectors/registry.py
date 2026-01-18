"""Adapter registry for selecting adapters by target type.

Per DEC-V0-ADAPTERS-PER-TARGET: normalization via per-target adapters.
"""

from __future__ import annotations

from typing import ClassVar

from mantora.connectors.bigquery import BigQueryAdapter
from mantora.connectors.databricks import DatabricksAdapter
from mantora.connectors.duckdb import DuckDBAdapter
from mantora.connectors.interface import Adapter, BaseAdapter, StepCategory
from mantora.connectors.postgres import PostgresAdapter
from mantora.connectors.snowflake import SnowflakeAdapter


class GenericAdapter(BaseAdapter):
    """Fallback adapter for unknown target types.

    Provides basic normalization without target-specific knowledge.
    """

    @property
    def target_type(self) -> str:
        return "generic"

    # Generic tool patterns
    _tool_categories: ClassVar[dict[str, StepCategory]] = {
        "query": "query",
        "execute": "query",
        "run": "query",
        "describe": "schema",
        "schema": "schema",
        "list": "list",
        "tables": "list",
    }


# Registry of known adapters
_ADAPTERS: dict[str, type[Adapter]] = {
    "duckdb": DuckDBAdapter,
    "postgres": PostgresAdapter,
    "postgresql": PostgresAdapter,  # Alias
    "pg": PostgresAdapter,  # Alias
    "snowflake": SnowflakeAdapter,
    "sf": SnowflakeAdapter,  # Alias
    "bigquery": BigQueryAdapter,
    "bq": BigQueryAdapter,  # Alias
    "databricks": DatabricksAdapter,
    "databricks_sql": DatabricksAdapter,  # Alias
    "generic": GenericAdapter,
}

# Singleton instances (adapters are stateless)
_adapter_instances: dict[str, Adapter] = {}


def get_adapter(target_type: str) -> Adapter:
    """Get an adapter for the given target type.

    Args:
        target_type: The type of target (e.g., 'duckdb', 'postgres').

    Returns:
        An adapter instance for the target type.
        Falls back to GenericAdapter if type is unknown.
    """
    # Normalize type name
    normalized = target_type.lower().strip()

    # Return cached instance if available
    if normalized in _adapter_instances:
        return _adapter_instances[normalized]

    # Get adapter class, defaulting to generic
    adapter_cls = _ADAPTERS.get(normalized, GenericAdapter)

    # Create and cache instance
    instance = adapter_cls()
    _adapter_instances[normalized] = instance

    return instance


def register_adapter(target_type: str, adapter_cls: type[Adapter]) -> None:
    """Register a custom adapter for a target type.

    Args:
        target_type: The type of target this adapter handles.
        adapter_cls: The adapter class to register.
    """
    normalized = target_type.lower().strip()
    _ADAPTERS[normalized] = adapter_cls

    # Clear cached instance if exists
    _adapter_instances.pop(normalized, None)


def list_adapters() -> list[str]:
    """List all registered adapter types."""
    return sorted(_ADAPTERS.keys())
