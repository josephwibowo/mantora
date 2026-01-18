from __future__ import annotations

from typing import Any
from uuid import UUID

from mantora.casts.models import TableCast
from mantora.config.settings import Caps
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore


def export_cast_md(*, store: SessionStore, cast_id: UUID, caps: Caps) -> str:
    """Export a cast as deterministic, human-readable Markdown.

    Per PRI-HARD-CAPS-ALWAYS: output is byte-capped.
    """
    c = store.get_cast(cast_id)
    if c is None:
        raise KeyError(cast_id)

    parts: list[str] = []
    parts.append(f"# Cast: {c.title}\n\n")
    parts.append(f"- Cast ID: `{c.id}`\n")
    parts.append(f"- Session ID: `{c.session_id}`\n")
    parts.append(f"- Created: `{c.created_at.isoformat()}`\n")
    parts.append(f"- Kind: `{c.kind}`\n")
    parts.append(f"- Evidence (origin_step_id): `{c.origin_step_id}`\n")
    if c.origin_step_ids:
        parts.append(
            f"- Evidence (origin_step_ids): {', '.join(f'`{sid}`' for sid in c.origin_step_ids)}\n"
        )

    if isinstance(c, TableCast):
        sql, sql_truncated = cap_text(c.sql, max_bytes=caps.max_preview_payload_bytes)
        parts.append("\n## Table\n\n")
        parts.append("**SQL**\n\n```sql\n")
        parts.append(sql.rstrip("\n"))
        parts.append("\n```\n")
        if sql_truncated:
            parts.append("_SQL truncated._\n")
        parts.append(f"\n- Rows shown: {len(c.rows)}\n")
        if c.total_rows is not None:
            parts.append(f"- Total rows: {c.total_rows}\n")
        if c.truncated:
            parts.append("- Table payload truncated (rows/cols) by caps.\n")

        raw_rows = _stable_json(c.rows)
        capped_rows, rows_truncated = cap_text(raw_rows, max_bytes=caps.max_preview_payload_bytes)
        parts.append("\n**Rows (JSON)**\n\n```json\n")
        parts.append(capped_rows.rstrip("\n"))
        parts.append("\n```\n")
        if rows_truncated:
            parts.append("_Rows JSON truncated._\n")

    raw = "".join(parts)
    capped, truncated = cap_text(raw, max_bytes=caps.max_preview_payload_bytes)
    if not truncated:
        return capped

    marker = "\n\n---\n\n_Export truncated due to caps._\n"
    recapped, _ = cap_text(capped + marker, max_bytes=caps.max_preview_payload_bytes)
    return recapped


def _stable_json(value: Any) -> str:
    import json

    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ": "), indent=2)
        + "\n"
    )
