from __future__ import annotations

import re
from typing import Final

from mantora.policy.sql_guard import SQLWarning

_FROM_JOIN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_.$\"`]+)", re.IGNORECASE
)


def lint_sql(sql: str) -> list[SQLWarning]:
    """Lint SQL for common best-practice violations.

    Uses sqlglot for precise parsing. Returns a list of warnings.
    """
    warnings = _lint_sqlglot(sql)
    if warnings is None:
        # Fallback to regex-based heuristics if parsing fails (or sqlglot missing)
        return _lint_regex(sql)
    return sorted(set(warnings))


def extract_tables_touched(sql: str) -> list[str] | None:
    """Best-effort table extraction for a SQL snippet.

    Uses sqlglot when available; falls back to conservative regex extraction.
    """
    tables = _extract_tables_sqlglot(sql) or _extract_tables_regex(sql)
    if not tables:
        return None
    # Preserve a stable, deterministic order.
    return sorted(set(tables))


def _lint_sqlglot(sql: str) -> list[SQLWarning] | None:
    try:
        import sqlglot
        from sqlglot import expressions as exp
    except ImportError:
        return None

    try:
        expressions = sqlglot.parse(sql)
    except Exception:
        # If parsing fails, return None so we can fall back to regex
        return None

    warnings: set[SQLWarning] = set()

    for expression in expressions:
        if expression is None:
            continue

        # Check for multiple statements
        if len(expressions) > 1:
            warnings.add(SQLWarning.MULTI_STATEMENT)

        # Walk the AST
        for node in expression.walk():
            # Check: SELECT *
            if isinstance(node, exp.Star):
                # Ensure it's part of a SELECT (not count(*))
                # sqlglot represents SELECT * as Select(expressions=[Star()])
                parent = node.parent
                if isinstance(parent, exp.Select):
                    warnings.add(SQLWarning.SELECT_STAR)

            # Check: DELETE without WHERE
            if isinstance(node, exp.Delete) and not node.args.get("where"):
                warnings.add(SQLWarning.DELETE_NO_WHERE)

            # Check: SELECT without LIMIT
            # Note: This is tricky because LIMIT might be on the main query,
            # but subqueries might not need it. We only check top-level queries or
            # significant subqueries?
            # For now, let's look at the top-level expression if it's a SELECT.
            if isinstance(node, exp.Select) and node is expression:
                # If there's a WHERE, we often forgive missing LIMIT (filtering)
                has_where = bool(node.args.get("where"))
                has_limit = bool(node.args.get("limit"))
                if not has_limit and not has_where:
                    warnings.add(SQLWarning.NO_LIMIT)

            # Check: DDL/DML detection for tagging?
            # (We use this for warnings in receipt too)
            if isinstance(node, (exp.Create, exp.Drop, exp.Alter)):
                warnings.add(SQLWarning.DDL)
            if isinstance(node, (exp.Insert, exp.Update, exp.Delete)):
                warnings.add(SQLWarning.DML)

    return list(warnings)


def _lint_regex(sql: str) -> list[SQLWarning]:
    """Fallback regex-based linting (reusing logic conceptually similar to sql_guard).

    We duplicate minimal logic here to avoid circular imports or heavy coupling,
    or we could import helper functions from sql_guard if refactored.
    For now, implementing basic checks locally is safer isolation.
    """
    warnings: set[SQLWarning] = set()
    upper = sql.upper()

    # Simple heuristics
    if "SELECT" in upper and "*" in upper and "SELECT *" in upper:  # Rough approximation
        warnings.add(SQLWarning.SELECT_STAR)

    if "DELETE" in upper and "WHERE" not in upper:
        warnings.add(SQLWarning.DELETE_NO_WHERE)

    if "SELECT" in upper and "LIMIT" not in upper and "WHERE" not in upper:
        warnings.add(SQLWarning.NO_LIMIT)

    return list(warnings)


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
    # Re-use guard's robust multiline detection if possible, or keep simple here.
    matches = _FROM_JOIN_PATTERN.findall(sql)
    if not matches:
        return None
    cleaned: list[str] = []
    for m in matches:
        raw = m.strip().strip('"').strip("`")
        if raw:
            cleaned.append(raw)
    return cleaned or None
