from __future__ import annotations

from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from mantora.casts.models import TableCast
from mantora.config.settings import Caps
from mantora.models.events import ObservedStep, Session
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore

_PR_RECEIPT_CAP_BYTES: Final[int] = 100 * 1024
_SQL_HEAD_CHARS: Final[int] = 1000
_SQL_TAIL_CHARS: Final[int] = 500
_MAX_SQL_SNIPPETS: Final[int] = 5


class ReceiptResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    markdown: str
    truncated: bool
    included_data: bool


def generate_pr_receipt(
    *,
    store: SessionStore,
    session_id: UUID,
    caps: Caps,
    include_data: bool = False,
) -> ReceiptResult:
    session = store.get_session(session_id)
    if session is None:
        raise KeyError(session_id)

    steps = list(store.list_steps(session_id))
    casts = list(store.list_casts(session_id)) if include_data else []

    status = _derive_status(steps)
    tables = _union_tables(steps)
    warnings = _union_warnings(steps)
    sql_snippets = _extract_sql_snippets(steps)

    parts: list[str] = []
    parts.append("<details>\n")
    parts.append(f"<summary>Mantora receipt — {status}</summary>\n\n")

    parts.append(_format_header(session))
    parts.append(_format_context(session))
    parts.append(_format_summary(steps, tables=tables, warnings=warnings, status=status))

    if sql_snippets:
        parts.append("\n**SQL snippets (capped)**\n\n")
        for idx, sql in enumerate(sql_snippets, start=1):
            parts.append(f"_{idx}._\n\n```sql\n{sql.rstrip()}\n```\n")
        if len(sql_snippets) >= _MAX_SQL_SNIPPETS:
            parts.append(f"\n_Only the first {_MAX_SQL_SNIPPETS} snippets are included._\n")

    if include_data and casts:
        parts.append("\n**Sample data (capped)**\n\n")
        for c in casts[:3]:
            parts.append(f"- Cast: `{c.title}` (`{c.kind}`)\n")
            parts.append(f"  - Evidence: `{c.origin_step_id}`\n")
            if isinstance(c, TableCast):
                parts.append("  - Rows (JSON):\n\n")
                raw = _stable_json(c.rows[: min(len(c.rows), 5)])
                capped, truncated = cap_text(raw, max_bytes=8 * 1024)
                parts.append("```json\n")
                parts.append(capped.rstrip("\n"))
                parts.append("\n```\n")
                if truncated or c.truncated:
                    parts.append("_Sample data truncated._\n")

    parts.append("\n</details>\n")

    raw = "".join(parts)
    max_bytes = min(caps.max_preview_payload_bytes, _PR_RECEIPT_CAP_BYTES)
    capped, truncated = cap_text(raw, max_bytes=max_bytes)
    return ReceiptResult(markdown=capped, truncated=truncated, included_data=include_data)


def _format_header(session: Session) -> str:
    title = session.title or str(session.id)
    return (
        f"**Session**: `{title}`\n\n"
        f"- ID: `{session.id}`\n"
        f"- Created: `{session.created_at.isoformat()}`\n"
    )


def _format_context(session: Session) -> str:
    ctx = session.context
    if ctx is None:
        return ""

    items: list[str] = []
    if ctx.repo_name:
        items.append(f"- Repo: `{ctx.repo_name}`\n")
    if ctx.branch:
        items.append(f"- Branch: `{ctx.branch}`\n")
    if ctx.commit:
        items.append(f"- Commit: `{ctx.commit}`\n")
    if ctx.dirty is not None:
        items.append(f"- Dirty: `{ctx.dirty}`\n")
    if ctx.tag:
        items.append(f"- Tag: `{ctx.tag}`\n")
    if not items:
        return ""

    return "\n**Context**\n\n" + "".join(items)


def _format_summary(
    steps: list[ObservedStep],
    *,
    tables: list[str],
    warnings: list[str],
    status: str,
) -> str:
    tool_calls = sum(1 for s in steps if s.kind == "tool_call")
    blocks = sum(1 for s in steps if s.kind == "blocker")
    errors = sum(1 for s in steps if s.status == "error")
    duration_ms_total = sum(s.duration_ms or 0 for s in steps)

    parts: list[str] = []
    parts.append("\n**Summary**\n\n")
    parts.append(f"- Status: `{status}`\n")
    parts.append(f"- Tool calls: `{tool_calls}`\n")
    if duration_ms_total:
        parts.append(f"- Duration (ms): `{duration_ms_total}`\n")
    if blocks:
        parts.append(f"- Blocks: `{blocks}`\n")
    if errors:
        parts.append(f"- Errors: `{errors}`\n")
    if warnings:
        parts.append(f"- Warnings: `{', '.join(warnings)}`\n")
    if tables:
        parts.append(f"- Tables touched: `{', '.join(tables)}`\n")
    return "".join(parts)


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


def _extract_sql_snippets(steps: list[ObservedStep]) -> list[str]:
    snippets: list[str] = []
    for s in steps:
        raw = _get_step_sql(s)
        if not raw:
            continue
        snippets.append(_truncate_sql(raw))
        if len(snippets) >= _MAX_SQL_SNIPPETS:
            break
    return snippets


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


def _stable_json(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), indent=2)
