"""SQL guard for protective mode enforcement.

Per DEC-V0-SAFETY-MODES: protective default, transparent optional.
Per PRI-PROTECTIVE-DEFAULT: protective is default.

Classifies SQL statements and detects potentially destructive operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Final

from mantora.config.settings import PolicyConfig

# Keywords that indicate destructive/mutating SQL operations
# Conservative list - may produce false positives on edge cases
_DESTRUCTIVE_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "UPSERT",
        "REPLACE",
        "TRUNCATE",
        "DROP",
        "CREATE",
        "ALTER",
        "GRANT",
        "REVOKE",
        "COPY",
        "LOAD",
        "VACUUM",
        "REINDEX",
        "CLUSTER",
        "REFRESH",
        "CALL",
        "EXEC",
        "EXECUTE",
    }
)

# Pattern to match destructive keywords at word boundaries (case-insensitive)
_DESTRUCTIVE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(" + "|".join(_DESTRUCTIVE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


class SQLClassification(str, Enum):
    """Classification of SQL statement safety."""

    read_only = "read_only"
    destructive = "destructive"
    unknown = "unknown"


class SQLRiskLevel(str, Enum):
    """Risk level for a SQL statement in protective mode."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    CRITICAL = "CRITICAL"


class SQLWarning(str, Enum):
    """Specific warnings for SQL queries."""

    NO_LIMIT = "NO_LIMIT"  # SELECT without LIMIT clause
    SELECT_STAR = "SELECT_STAR"  # Uses SELECT *
    MULTI_STATEMENT = "MULTI_STATEMENT"  # Multiple statements
    DDL = "DDL"  # Data definition (CREATE, ALTER, DROP)
    DML = "DML"  # Data manipulation (INSERT, UPDATE, DELETE)
    DELETE_NO_WHERE = "DELETE_NO_WHERE"  # DELETE without WHERE clause
    APPROACHED_ROW_CAP = "APPROACHED_ROW_CAP"  # Result near row limit


@dataclass(frozen=True)
class SQLGuardResult:
    """Result of SQL guard analysis."""

    classification: SQLClassification
    is_multi_statement: bool
    risk_level: SQLRiskLevel
    warnings: list[SQLWarning]
    reason: str | None = None

    @property
    def is_safe(self) -> bool:
        """Whether the SQL is considered safe for protective mode."""
        return self.classification == SQLClassification.read_only and not self.is_multi_statement


def _detect_multi_statement(sql: str) -> bool:
    """Detect if SQL contains multiple statements.

    V0 heuristic: presence of semicolon followed by non-whitespace.
    This is conservative and may have false positives (e.g., semicolons in strings).
    Future versions can use proper SQL parsing.
    """
    # Strip trailing whitespace and semicolons
    stripped = sql.rstrip().rstrip(";").rstrip()

    # Check if there's still a semicolon in the remaining SQL
    return ";" in stripped


def _detect_delete_without_where(sql: str) -> bool:
    """Heuristic: flag DELETE statements that do not contain a WHERE clause.

    Conservative: does not try to parse SQL; looks for WHERE anywhere after DELETE.
    """
    upper_sql = sql.upper()
    if "DELETE" not in upper_sql:
        return False
    # Quick check that it's actually a DELETE statement (not a string literal; known limitation).
    if not re.search(r"\bDELETE\b", upper_sql):
        return False
    # If there's no WHERE keyword anywhere, treat as high risk.
    return re.search(r"\bWHERE\b", upper_sql) is None


def _classify_sql(sql: str) -> SQLClassification:
    """Classify SQL statement as read-only, destructive, or unknown.

    Uses keyword-based heuristics. Conservative approach:
    - If destructive keywords found -> destructive
    - If only SELECT/WITH/EXPLAIN/SHOW/DESCRIBE -> read_only
    - Otherwise -> unknown
    """
    upper_sql = sql.upper().strip()

    # Check for destructive keywords
    if _DESTRUCTIVE_PATTERN.search(sql):
        return SQLClassification.destructive

    # Check for read-only patterns
    # Allow SELECT, WITH (CTEs), EXPLAIN, SHOW, DESCRIBE
    read_only_starts = ("SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE", "PRAGMA")
    if any(upper_sql.startswith(kw) for kw in read_only_starts):
        return SQLClassification.read_only

    # Unknown - could be vendor-specific or edge case
    return SQLClassification.unknown


def _detect_select_star(sql: str) -> bool:
    """Detect if SQL uses SELECT *."""
    return bool(re.search(r"\bSELECT\s+\*", sql, re.IGNORECASE))


def _detect_no_limit(sql: str) -> bool:
    """Detect if SELECT query has no LIMIT clause.

    V0 heuristic: if a WHERE clause is present, we do not warn for lack of LIMIT.
    This reduces noise for common filtered exploration queries.
    """
    upper_sql = sql.upper()
    if not re.search(r"\bSELECT\b", upper_sql):
        return False
    if re.search(r"\bWHERE\b", upper_sql):
        return False
    return not re.search(r"\bLIMIT\b", upper_sql)


def _detect_ddl(sql: str) -> bool:
    """Detect DDL operations (CREATE, ALTER, DROP)."""
    ddl_pattern = r"\b(CREATE|ALTER|DROP)\b"
    return bool(re.search(ddl_pattern, sql, re.IGNORECASE))


def _detect_dml(sql: str) -> bool:
    """Detect DML operations (INSERT, UPDATE, DELETE)."""
    dml_pattern = r"\b(INSERT|UPDATE|DELETE)\b"
    return bool(re.search(dml_pattern, sql, re.IGNORECASE))


def analyze_sql(sql: str) -> SQLGuardResult:
    """Analyze SQL for safety in protective mode.

    Args:
        sql: The SQL statement to analyze.

    Returns:
        SQLGuardResult with classification, multi-statement detection, and warnings.
    """
    if not sql or not sql.strip():
        return SQLGuardResult(
            classification=SQLClassification.unknown,
            is_multi_statement=False,
            risk_level=SQLRiskLevel.MEDIUM,
            warnings=[],
            reason="Empty SQL",
        )

    is_multi = _detect_multi_statement(sql)
    classification = _classify_sql(sql)
    delete_without_where = _detect_delete_without_where(sql)

    # Collect all warnings
    warnings: list[SQLWarning] = []

    if is_multi:
        warnings.append(SQLWarning.MULTI_STATEMENT)
    if _detect_select_star(sql):
        warnings.append(SQLWarning.SELECT_STAR)
    if _detect_no_limit(sql):
        warnings.append(SQLWarning.NO_LIMIT)
    if delete_without_where:
        warnings.append(SQLWarning.DELETE_NO_WHERE)
    if _detect_ddl(sql):
        warnings.append(SQLWarning.DDL)
    if _detect_dml(sql):
        warnings.append(SQLWarning.DML)

    reason = None
    if is_multi:
        reason = "Multi-statement SQL detected"
    elif delete_without_where:
        reason = "DELETE without WHERE detected"
    elif classification == SQLClassification.destructive:
        reason = "Destructive SQL operation detected"
    elif classification == SQLClassification.unknown:
        reason = "Unable to classify SQL as safe"

    risk_level: SQLRiskLevel
    if is_multi or delete_without_where or classification == SQLClassification.destructive:
        risk_level = SQLRiskLevel.CRITICAL
    elif classification == SQLClassification.unknown:
        risk_level = SQLRiskLevel.MEDIUM
    else:
        risk_level = SQLRiskLevel.LOW

    return SQLGuardResult(
        classification=classification,
        is_multi_statement=is_multi,
        risk_level=risk_level,
        warnings=warnings,
        reason=reason,
    )


def should_block_sql(sql: str, *, policy: PolicyConfig) -> tuple[bool, str | None]:
    """Determine if SQL should be blocked based on policy settings."""
    if not policy.protective_mode:
        return (False, None)

    result = analyze_sql(sql)
    warnings = set(result.warnings)

    if result.is_multi_statement and policy.block_multi_statement:
        return (True, result.reason or "Multi-statement SQL detected")

    if SQLWarning.DELETE_NO_WHERE in warnings and policy.block_delete_without_where:
        return (True, result.reason or "DELETE without WHERE detected")

    if SQLWarning.DDL in warnings and policy.block_ddl:
        return (True, "DDL statements are blocked in protective mode")

    if SQLWarning.DML in warnings and policy.block_dml:
        return (True, "DML statements are blocked in protective mode")

    if result.classification == SQLClassification.destructive and not (
        SQLWarning.DDL in warnings or SQLWarning.DML in warnings
    ):
        return (True, result.reason or "Destructive SQL operation detected")

    return (False, None)
