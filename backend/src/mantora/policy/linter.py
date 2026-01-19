from __future__ import annotations

import re
from typing import Final

_FROM_JOIN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_.$\"`]+)", re.IGNORECASE
)


def extract_tables_touched(sql: str) -> list[str] | None:
    """Best-effort table extraction for a SQL snippet.

    Uses sqlglot when available; falls back to conservative regex extraction.
    """
    tables = _extract_tables_sqlglot(sql) or _extract_tables_regex(sql)
    if not tables:
        return None
    # Preserve a stable, deterministic order.
    return sorted(set(tables))


def _extract_tables_sqlglot(sql: str) -> list[str] | None:
    try:
        import sqlglot
        from sqlglot import expressions as exp
    except Exception:
        return None

    try:
        expressions = sqlglot.parse(sql)
    except Exception:
        return None

    tables: list[str] = []
    for expression in expressions:
        if expression is None:
            continue
        for table in expression.find_all(exp.Table):
            name = table.name
            if not name:
                continue
            parts = [p for p in [table.catalog, table.db, name] if p]
            tables.append(".".join(parts))
    return tables or None


def _extract_tables_regex(sql: str) -> list[str] | None:
    matches = _FROM_JOIN_PATTERN.findall(sql)
    if not matches:
        return None
    cleaned: list[str] = []
    for m in matches:
        raw = m.strip().strip('"').strip("`")
        if raw:
            cleaned.append(raw)
    return cleaned or None
