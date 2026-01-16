from __future__ import annotations

from typing import Any

from mantora.config.settings import PolicyConfig
from mantora.connectors.interface import Adapter

SAFE_READONLY_TOOLS: set[str] = {
    "session_start",
    "session_end",
    "session_current",
    "cast_table",
}


def is_tool_known_safe(
    tool_name: str,
    adapter: Adapter,
    *,
    arguments: dict[str, Any] | None = None,
    policy: PolicyConfig | None = None,
) -> bool:
    """Return True if the tool is known to be safe in protective mode."""
    if tool_name in SAFE_READONLY_TOOLS:
        return True

    category = adapter.categorize_tool(tool_name)
    if category in ("schema", "list"):
        return True

    if arguments is None:
        return False

    evidence = adapter.extract_evidence(tool_name, arguments, None)
    raw_sql = evidence.get("sql")
    if raw_sql is None:
        return False

    _ = raw_sql if isinstance(raw_sql, str) else str(raw_sql)
    return True
