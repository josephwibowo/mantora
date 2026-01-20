from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContextInfo:
    """Git/repo context information."""

    repo_name: str | None
    branch: str | None
    commit: str | None
    dirty: bool | None
    tag: str | None


@dataclass
class SummaryRow:
    """Summary table row data."""

    status: str
    tables: str
    warnings: str
    blocks: str


@dataclass
class TimelineRow:
    """Single row in the timeline table."""

    abs_time: str  # "14:32:05"
    rel_time: str  # "57ms"
    step_num: int
    step_type: str  # "QUERY", "MUTATION", "CAST", "TOOL"
    status_emoji: str  # "✅", "⚠️", "🛑"
    table: str
    note: str


@dataclass
class CastDetail:
    """CAST evidence to display inline under a query."""

    title: str
    kind: str
    table_md: str  # Pre-rendered markdown table


@dataclass
class SqlDetail:
    """SQL snippet with metadata and inline casts."""

    step_label: str  # "Step 1, 2 — QUERY (×2)"  # noqa: RUF003
    meta: str  # "(✅, 12ms)"
    sql: str
    casts: list[CastDetail]


@dataclass
class ReceiptContext:
    """Complete context for rendering the receipt template."""

    status_emoji: str
    status_label: str
    session_title: str
    session_id: str
    created_at: str
    context: ContextInfo | None
    summary_row: SummaryRow
    secondary_stats: str
    timeline: list[TimelineRow]
    sql_details: list[SqlDetail]
    include_data: bool
