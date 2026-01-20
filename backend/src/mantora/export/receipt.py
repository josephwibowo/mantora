from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final, Literal
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict

from mantora.casts.models import TableCast
from mantora.config.settings import Caps
from mantora.export.receipt_context import (
    CastDetail,
    ContextInfo,
    ReceiptContext,
    SqlDetail,
    SummaryRow,
    TimelineRow,
)
from mantora.models.events import ObservedStep, Session
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore

_PR_RECEIPT_CAP_BYTES: Final[int] = 100 * 1024
_SQL_HEAD_CHARS: Final[int] = 1000
_SQL_TAIL_CHARS: Final[int] = 500
_MAX_SQL_SNIPPETS: Final[int] = 5
_STATUS_EMOJI: Final[dict[str, str]] = {"blocked": "🛑", "warnings": "⚠️", "clean": "✅"}

_TEMPLATE_GFM: Final[str] = "receipt.md.j2"
_TEMPLATE_PLAIN: Final[str] = "receipt_plain.j2"

ReceiptFormat = Literal["gfm", "plain"]

# Initialize Jinja2 environment
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


class ReceiptResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    markdown: str
    truncated: bool
    included_data: bool
    format: ReceiptFormat


def generate_pr_receipt(
    *,
    store: SessionStore,
    session_id: UUID,
    caps: Caps,
    include_data: bool = False,
    format: ReceiptFormat = "gfm",
) -> ReceiptResult:
    session = store.get_session(session_id)
    if session is None:
        raise KeyError(session_id)

    steps = list(store.list_steps(session_id))
    casts = list(store.list_casts(session_id)) if include_data else []

    # Build context for template
    context = _build_receipt_context(session, steps, casts, include_data)

    # Render template
    template_name = _TEMPLATE_GFM if format == "gfm" else _TEMPLATE_PLAIN
    template = _jinja_env.get_template(template_name)
    raw = template.render(**context.__dict__)

    # Apply byte cap
    max_bytes = min(caps.max_preview_payload_bytes, _PR_RECEIPT_CAP_BYTES)
    capped, truncated = cap_text(raw, max_bytes=max_bytes)
    return ReceiptResult(
        markdown=capped,
        truncated=truncated,
        included_data=include_data,
        format=format,
    )


def _build_receipt_context(
    session: Session,
    steps: list[ObservedStep],
    casts: Sequence[TableCast | object],
    include_data: bool,
) -> ReceiptContext:
    """Build the complete context object for template rendering."""
    status = _derive_status(steps)
    tables = _union_tables(steps)
    warnings = _union_warnings(steps)

    # Build context info
    ctx_info = None
    if session.context:
        ctx = session.context
        ctx_info = ContextInfo(
            repo_name=ctx.repo_name,
            branch=ctx.branch,
            commit=ctx.commit,
            dirty=ctx.dirty,
            tag=ctx.tag,
        )

    # Build summary row
    emoji = _STATUS_EMOJI.get(status, "")
    status_text = f"{emoji} {status}" if emoji else status
    tables_text = ", ".join(f"`{t}`" for t in tables) if tables else "—"
    warnings_text = ", ".join(warnings) if warnings else "—"
    blocks = sum(1 for s in steps if s.kind == "blocker")
    blocks_text = str(blocks) if blocks else "—"

    summary_row = SummaryRow(
        status=status_text,
        tables=tables_text,
        warnings=warnings_text,
        blocks=blocks_text,
    )

    # Build secondary stats
    tool_calls = sum(1 for s in steps if s.kind == "tool_call")
    errors = sum(1 for s in steps if s.status == "error")
    duration_ms_total = sum(s.duration_ms or 0 for s in steps)

    secondary_stats_parts = []
    secondary_stats_parts.append(f"{tool_calls} tool call{'s' if tool_calls != 1 else ''}")
    if duration_ms_total:
        secondary_stats_parts.append(f"{duration_ms_total} ms")
    if errors:
        secondary_stats_parts.append(f"{errors} error{'s' if errors != 1 else ''}")
    secondary_stats = " · ".join(secondary_stats_parts)

    # Build timeline
    timeline = _build_timeline(steps, session)

    # Group casts by origin step ID for inline display
    casts_by_step_id: dict[UUID, list[TableCast | object]] = {}
    if include_data and casts:
        for c in casts:
            origin_id = getattr(c, "origin_step_id", None)
            if origin_id:
                if origin_id not in casts_by_step_id:
                    casts_by_step_id[origin_id] = []
                casts_by_step_id[origin_id].append(c)

    # Build SQL details with inline casts
    sql_details = _build_sql_details(steps, session.created_at, casts_by_step_id)

    # Build status label
    status_label = status.capitalize()
    if status == "blocked":
        status_label += " • Protective Mode"

    return ReceiptContext(
        status_emoji=_STATUS_EMOJI.get(status, ""),
        status_label=status_label,
        session_title=session.title or str(session.id),
        session_id=str(session.id),
        created_at=session.created_at.isoformat(),
        context=ctx_info,
        summary_row=summary_row,
        secondary_stats=secondary_stats,
        timeline=timeline,
        sql_details=sql_details,
        include_data=include_data,
    )


def _build_timeline(steps: list[ObservedStep], session: Session) -> list[TimelineRow]:
    """Build timeline rows from steps."""
    timeline_rows = []
    session_start = session.created_at

    for idx, step in enumerate(steps, start=1):
        # Compute relative timestamp
        delta_ms = int((step.created_at - session_start).total_seconds() * 1000)
        rel_time = f"{delta_ms}ms"

        # Absolute time (HH:MM:SS)
        abs_time = step.created_at.strftime("%H:%M:%S")

        # Determine type
        step_type = _get_step_type(step)

        # Determine status emoji
        status_emoji = _get_step_status_emoji(step)

        # Get first table or fallback
        table = step.tables_touched[0] if step.tables_touched else "—"

        # Generate note
        note = _get_step_note(step)

        timeline_rows.append(
            TimelineRow(
                abs_time=abs_time,
                rel_time=rel_time,
                step_num=idx,
                step_type=step_type,
                status_emoji=status_emoji,
                table=table,
                note=note,
            )
        )

    return timeline_rows


def _build_sql_details(
    steps: list[ObservedStep],
    session_start: datetime,
    casts_by_step_id: dict[UUID, list[TableCast | object]],
) -> list[SqlDetail]:
    """Build SQL details with deduplication and inline casts."""
    sql_details = []

    # Group by SQL hash to deduplicate
    grouped: dict[str, list[tuple[int, ObservedStep]]] = {}

    for idx, step in enumerate(steps, start=1):
        raw_sql = _get_step_sql(step)
        if not raw_sql:
            continue

        sql_key = _truncate_sql(raw_sql)
        if sql_key not in grouped:
            grouped[sql_key] = []
        grouped[sql_key].append((idx, step))

    # Build SqlDetail objects
    for sql_key, items in grouped.items():
        _first_idx, first_step = items[0]

        # Collect all step numbers and IDs
        step_numbers = [i for i, _ in items]
        step_ids = [s.id for _, s in items]

        # Format step label
        step_nums_str = ", ".join(str(n) for n in step_numbers)
        if len(step_numbers) > 3:
            step_nums_str = f"{step_numbers[0]}..{step_numbers[-1]} ({len(step_numbers)}x)"

        step_label = f"**Step {step_nums_str} — {_get_step_type(first_step)}"

        if len(step_numbers) > 1:
            step_label += f" (×{len(step_numbers)})"  # noqa: RUF001

        step_label += "**"

        # Format meta (status, duration, and t+)
        meta_parts = []
        if first_step.kind == "blocker":
            meta_parts.append("🛑 Blocked")
        elif first_step.warnings:
            meta_parts.append(f"⚠️ {first_step.warnings[0]}")
        else:
            meta_parts.append("✅")

        if first_step.duration_ms is not None:
            meta_parts.append(f"{first_step.duration_ms}ms")

        delta_ms = int((first_step.created_at - session_start).total_seconds() * 1000)
        meta_parts.append(f"t+{delta_ms}ms")

        meta = f"({', '.join(meta_parts)})"

        # Build inline casts for these steps
        cast_details = []
        for step_id in step_ids:
            step_casts = casts_by_step_id.get(step_id, [])
            for c in step_casts:
                title = getattr(c, "title", "Sample data")
                kind = getattr(c, "kind", "cast")
                table_md = _render_cast_table(c)
                cast_details.append(CastDetail(title=title, kind=kind, table_md=table_md))

        sql_details.append(
            SqlDetail(
                step_label=step_label,
                meta=meta,
                sql=sql_key,
                casts=cast_details,
            )
        )

    # Sort by first step number to maintain timeline order
    sql_details.sort(key=lambda x: int(x.step_label.split()[1].split(",")[0]))

    # Limit to _MAX_SQL_SNIPPETS
    return sql_details[:_MAX_SQL_SNIPPETS]


def _render_cast_table(cast: TableCast | object) -> str:
    """Render a TableCast as markdown table."""
    if not isinstance(cast, TableCast):
        origin_id = getattr(cast, "origin_step_id", "?")
        return f"Evidence ID: `{origin_id}`"

    rows_to_show = cast.rows[: min(len(cast.rows), 5)]

    if not rows_to_show:
        return "_No rows._"

    keys = sorted(rows_to_show[0].keys())
    lines = []
    lines.append("| " + " | ".join(keys) + " |")
    lines.append("|" + "---|" * len(keys))
    for row in rows_to_show:
        lines.append("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")

    if len(cast.rows) > len(rows_to_show):
        lines.append("")
        lines.append(f"_... {len(cast.rows) - len(rows_to_show)} more rows ..._")

    return "\n".join(lines)


def _get_step_type(step: ObservedStep) -> str:
    """Determine the type label for a step."""
    if step.kind == "blocker":
        return "MUTATION"
    if step.name.startswith("cast_"):
        return "CAST"
    if step.name == "query":
        # Check if it's a mutation based on SQL
        if step.sql and step.sql.text:
            sql_upper = step.sql.text.strip().upper()
            if any(
                sql_upper.startswith(kw)
                for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]
            ):
                return "MUTATION"
        return "QUERY"
    return "TOOL"


def _get_step_status_emoji(step: ObservedStep) -> str:
    """Determine the status emoji for a step."""
    if step.kind == "blocker":
        return "🛑"
    if step.warnings:
        return "⚠️"
    return "✅"


def _get_step_note(step: ObservedStep) -> str:
    """Generate a concise note for the timeline."""
    notes = []

    if step.kind == "blocker":
        notes.append("DML blocked")
    elif step.warnings:
        # Use first warning as primary note
        notes.append(step.warnings[0])

        if (
            step.result is not None
            and step.result_rows_shown is not None
            and step.result_rows_shown > 0
        ):
            notes.append(f"{step.result_rows_shown} rows")

    if step.name.startswith("cast_") and step.result_rows_shown is not None:
        # Add row count if available
        notes.append(f"{step.result_rows_shown} rows")

    if not notes:
        # Fallback to step name if nothing else
        return step.name.replace("_", " ")

    return ", ".join(notes)


def _derive_status(steps: list[ObservedStep]) -> str:
    if any(s.kind == "blocker" for s in steps):
        return "blocked"
    if any(bool(s.warnings) for s in steps):
        return "warnings"
    return "clean"


def _union_tables(steps: list[ObservedStep]) -> list[str]:
    tables: set[str] = set()
    for s in steps:
        if s.tables_touched:
            tables.update(s.tables_touched)
    return sorted(tables)


def _union_warnings(steps: list[ObservedStep]) -> list[str]:
    warnings: set[str] = set()
    for s in steps:
        if s.warnings:
            warnings.update(s.warnings)
    return sorted(warnings)


def _get_step_sql(step: ObservedStep) -> str | None:
    if step.sql is not None and step.sql.text.strip():
        return step.sql.text
    if isinstance(step.args, dict):
        raw = step.args.get("sql")
        if isinstance(raw, str) and raw.strip():
            return raw
    return None


def _truncate_sql(sql: str) -> str:
    text = sql.strip()
    if len(text) <= _SQL_HEAD_CHARS + _SQL_TAIL_CHARS + 32:
        return text

    head = text[:_SQL_HEAD_CHARS].rstrip()
    tail = text[-_SQL_TAIL_CHARS:].lstrip()
    marker = "/* … truncated … */"
    if "VALUES" in text.upper():
        marker = "/* … values truncated … */"
    return f"{head}\n\n{marker}\n\n{tail}"
