from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mantora.casts.models import Cast, TableCast
from mantora.config.settings import Caps
from mantora.models.events import ObservedStep
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore

SCHEMA_VERSION = "mantora.session.v0"


def export_session_json(*, store: SessionStore, session_id: UUID, caps: Caps) -> str:
    """Export a session as a deterministic, timeline-ordered JSON payload.

    Per DEC-V0-EVIDENCE-NORMALIZED: exports are based on normalized store records.
    Per DEC-V0-REPLAY-TIMELINE: steps are exported in timeline order.
    Per PRI-HARD-CAPS-ALWAYS: export is bounded by caps.
    """
    session = store.get_session(session_id)
    if session is None:
        raise KeyError(session_id)

    steps_all = list(store.list_steps(session_id))
    casts_all = list(store.list_casts(session_id))

    max_items = caps.max_preview_rows
    steps = steps_all[:max_items]
    casts = casts_all[:max_items]

    steps_truncated = len(steps_all) > len(steps)
    casts_truncated = len(casts_all) > len(casts)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "session": {
            "id": str(session.id),
            "title": session.title,
            "created_at": session.created_at.isoformat(),
        },
        "caps": {
            "max_preview_rows": caps.max_preview_rows,
            "max_preview_payload_bytes": caps.max_preview_payload_bytes,
            "max_columns": caps.max_columns,
        },
        "truncation": {
            "steps_truncated": steps_truncated,
            "casts_truncated": casts_truncated,
            "max_items": max_items,
        },
        "steps": [_step_to_export(step=s, caps=caps) for s in steps],
        "casts": [_cast_to_export(c=c, caps=caps) for c in casts],
    }

    # Deterministic output: stable key ordering + stable separators.
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), indent=2)
        + "\n"
    )


def _step_to_export(*, step: ObservedStep, caps: Caps) -> dict[str, Any]:
    args_json, args_truncated = _json_value_to_capped_json(value=step.args, caps=caps)
    result_json, result_truncated = _json_value_to_capped_json(value=step.result, caps=caps)

    sql_text: str | None
    sql_truncated: bool
    if step.sql is None:
        sql_text = None
        sql_truncated = False
    else:
        sql_text, was_truncated = cap_text(step.sql.text, max_bytes=caps.max_preview_payload_bytes)
        sql_truncated = bool(step.sql.truncated or was_truncated)

    preview_text: str | None
    preview_truncated: bool
    if step.preview is None:
        preview_text = None
        preview_truncated = False
    else:
        capped, was_truncated = cap_text(
            step.preview.text, max_bytes=caps.max_preview_payload_bytes
        )
        preview_text = capped
        preview_truncated = bool(step.preview.truncated or was_truncated)

    return {
        "id": str(step.id),
        "created_at": step.created_at.isoformat(),
        "kind": step.kind,
        "name": step.name,
        "status": step.status,
        "duration_ms": step.duration_ms,
        "risk_level": step.risk_level,
        "warnings": step.warnings,
        "target_type": step.target_type,
        "tool_category": step.tool_category,
        "sql_text": sql_text,
        "sql_truncated": sql_truncated,
        "sql_classification": step.sql_classification,
        "policy_rule_ids": step.policy_rule_ids,
        "decision": step.decision,
        "result_rows_shown": step.result_rows_shown,
        "result_rows_total": step.result_rows_total,
        "captured_bytes": step.captured_bytes,
        "error_message": step.error_message,
        "args_json": args_json,
        "args_truncated": args_truncated,
        "result_json": result_json,
        "result_truncated": result_truncated,
        "preview_text": preview_text,
        "preview_truncated": preview_truncated,
    }


def _cast_to_export(*, c: Cast, caps: Caps) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": str(c.id),
        "created_at": c.created_at.isoformat(),
        "kind": c.kind,
        "title": c.title,
        "origin_step_id": str(c.origin_step_id),
        "origin_step_ids": [str(sid) for sid in c.origin_step_ids],
    }

    if isinstance(c, TableCast):
        rows_json, rows_truncated = _json_value_to_capped_json(value=c.rows, caps=caps)
        sql, sql_truncated = _cap_text_or_none(c.sql, caps=caps)
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

    # Union should be exhaustive, but keep safe fallback for unsupported kinds.
    return base


def _json_value_to_capped_json(*, value: Any, caps: Caps) -> tuple[str | None, bool]:
    if value is None:
        return None, False

    # Deterministic serialization.
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    capped, truncated = cap_text(raw, max_bytes=caps.max_preview_payload_bytes)
    return capped, truncated


def _cap_text_or_none(text: str | None, *, caps: Caps) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    capped, truncated = cap_text(text, max_bytes=caps.max_preview_payload_bytes)
    return capped, truncated
