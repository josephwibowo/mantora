from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mantora.casts.models import Cast, TableCast
from mantora.config.settings import Caps
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore

SCHEMA_VERSION = "mantora.cast.v0"


def export_cast_json(*, store: SessionStore, cast_id: UUID, caps: Caps) -> str:
    """Export a cast as a deterministic JSON payload.

    Per PRI-HARD-CAPS-ALWAYS: export is bounded by caps.
    """
    c = store.get_cast(cast_id)
    if c is None:
        raise KeyError(cast_id)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "cast": _cast_to_export(c=c, caps=caps),
        "caps": {
            "max_preview_rows": caps.max_preview_rows,
            "max_preview_payload_bytes": caps.max_preview_payload_bytes,
            "max_columns": caps.max_columns,
        },
    }

    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), indent=2)
        + "\n"
    )


def _cast_to_export(*, c: Cast, caps: Caps) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": str(c.id),
        "session_id": str(c.session_id),
        "created_at": c.created_at.isoformat(),
        "kind": c.kind,
        "title": c.title,
        "origin_step_id": str(c.origin_step_id),
        "origin_step_ids": [str(sid) for sid in c.origin_step_ids],
    }

    if isinstance(c, TableCast):
        rows_json, rows_truncated = _json_value_to_capped_json(value=c.rows, caps=caps)
        sql, sql_truncated = cap_text(c.sql, max_bytes=caps.max_preview_payload_bytes)
        base.update(
            {
                "sql": sql,
                "sql_truncated": sql_truncated,
                "rows_json": rows_json,
                "rows_truncated": bool(c.truncated or rows_truncated),
                "total_rows": c.total_rows,
            }
        )
    return base


def _json_value_to_capped_json(*, value: Any, caps: Caps) -> tuple[str | None, bool]:
    if value is None:
        return None, False

    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    capped, truncated = cap_text(raw, max_bytes=caps.max_preview_payload_bytes)
    return capped, truncated
