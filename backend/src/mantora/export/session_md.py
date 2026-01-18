from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from mantora.casts.models import Cast, TableCast
from mantora.config.settings import Caps
from mantora.models.events import ObservedStep, SessionSummary, StepDecision, TruncatedText
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore


@dataclass(frozen=True)
class MarkdownExportResult:
    content: str
    truncated: bool


def export_session_md(*, store: SessionStore, session_id: UUID, caps: Caps) -> str:
    """Export a session as a deterministic, human-readable Markdown report.

    Per DEC-V0-REPLAY-TIMELINE: timeline order is preserved.
    Per PRI-HARD-CAPS-ALWAYS: the output is byte-capped.
    """
    session = store.get_session(session_id)
    if session is None:
        raise KeyError(session_id)

    steps_all = list(store.list_steps(session_id))
    casts_all = list(store.list_casts(session_id))

    max_items = caps.max_preview_rows
    steps = steps_all[:max_items]
    casts = casts_all[:max_items]

    parts: list[str] = []
    parts.append(f"# Session: {session.title or str(session.id)}\n")
    parts.append(f"- ID: `{session.id}`\n")
    parts.append(f"- Created: `{session.created_at.isoformat()}`\n")
    parts.append(f"- Steps: {len(steps)} (of {len(steps_all)})\n")
    parts.append(f"- Casts: {len(casts)} (of {len(casts_all)})\n")
    parts.append("\n")

    summary = compute_session_summary(steps=steps_all, casts_count=len(casts_all))
    parts.append("## Summary\n\n")
    parts.append(f"- Tool calls: {summary.tool_calls}\n")
    parts.append(f"- Queries: {summary.queries}\n")
    parts.append(f"- Casts: {summary.casts}\n")
    parts.append(f"- Blocks: {summary.blocks}\n")
    parts.append(f"- Errors: {summary.errors}\n")
    parts.append(f"- Warnings: {summary.warnings}\n")
    parts.append("\n")

    parts.append("## Timeline\n\n")
    for idx, step in enumerate(steps, start=1):
        parts.append(_format_step(step=step, index=idx, caps=caps))

    parts.append("\n## Casts\n\n")
    if not casts:
        parts.append("_No casts._\n")
    else:
        for c in casts:
            parts.append(_format_cast(c=c, caps=caps))

    raw = "".join(parts)
    capped, truncated = cap_text(raw, max_bytes=caps.max_preview_payload_bytes)
    if not truncated:
        return capped

    # If we had to cap, append a deterministic marker (and re-cap once).
    marker = "\n\n---\n\n_Export truncated due to caps._\n"
    recapped, _ = cap_text(capped + marker, max_bytes=caps.max_preview_payload_bytes)
    return recapped


def _format_step(*, step: ObservedStep, index: int, caps: Caps) -> str:
    header = (
        f"### {index}. {step.name}\n\n"
        f"- Step ID: `{step.id}`\n"
        f"- At: `{step.created_at.isoformat()}`\n"
        f"- Kind: `{step.kind}`\n"
        f"- Status: `{step.status}`\n"
    )
    if step.duration_ms is not None:
        header += f"- Duration: `{step.duration_ms}ms`\n"
    if step.risk_level is not None:
        header += f"- Risk: `{step.risk_level}`\n"
    if step.warnings:
        header += f"- Warnings: `{', '.join(step.warnings)}`\n"
    if step.summary is not None:
        header += f"- Summary: {step.summary}\n"

    receipt = ""
    if step.target_type is not None:
        receipt += f"- Target: `{step.target_type}`\n"
    if step.tool_category is not None:
        receipt += f"- Category: `{step.tool_category}`\n"
    sql_classification = step.sql_classification
    if sql_classification is None and isinstance(step.args, dict):
        raw_classification = step.args.get("classification")
        if isinstance(raw_classification, str):
            sql_classification = raw_classification
    if sql_classification is not None:
        receipt += f"- SQL classification: `{sql_classification}`\n"
    policy_rule_ids = step.policy_rule_ids
    if policy_rule_ids is None and isinstance(step.args, dict):
        raw_rule_ids = step.args.get("policy_rule_ids")
        if isinstance(raw_rule_ids, list) and all(isinstance(x, str) for x in raw_rule_ids):
            policy_rule_ids = cast(list[str], raw_rule_ids)
    if policy_rule_ids:
        receipt += f"- Policy rules: `{', '.join(policy_rule_ids)}`\n"

    decision = step.decision
    if decision is None and isinstance(step.args, dict):
        raw_decision = step.args.get("decision")
        if raw_decision in ("pending", "allowed", "denied", "timeout"):
            decision = cast(StepDecision, raw_decision)
    if decision is not None:
        receipt += f"- Decision: `{decision}`\n"

    if step.kind in ("blocker", "blocker_decision") and isinstance(step.args, dict):
        request_id = step.args.get("request_id")
        reason = step.args.get("reason")
        if request_id:
            receipt += f"- Pending request: `{request_id}`\n"
        if reason:
            receipt += f"- Reason: {reason}\n"
    if step.result_rows_shown is not None:
        receipt += f"- Rows shown: {step.result_rows_shown}\n"
    if step.result_rows_total is not None:
        receipt += f"- Total rows: {step.result_rows_total}\n"
    if step.captured_bytes is not None:
        receipt += f"- Captured bytes: {step.captured_bytes}\n"
    if step.error_message is not None:
        receipt += f"- Error: {step.error_message}\n"

    body = ""
    if receipt:
        body += "\n**Receipt v1**\n\n" + receipt

    # Render SQL (query/cast/blocker steps).
    sql_value: TruncatedText | None = step.sql
    if sql_value is None and isinstance(step.args, dict):
        raw_sql = step.args.get("sql")
        if raw_sql is not None:
            sql_text, sql_truncated = cap_text(
                str(raw_sql), max_bytes=caps.max_preview_payload_bytes
            )
            sql_value = TruncatedText(text=sql_text, truncated=sql_truncated)

    if sql_value is not None:
        sql_text, was_truncated = cap_text(sql_value.text, max_bytes=caps.max_preview_payload_bytes)
        truncated = bool(sql_value.truncated or was_truncated)
        body += "\n**SQL**\n\n```sql\n" + sql_text.rstrip("\n") + "\n```\n"
        if truncated:
            body += "_SQL truncated._\n"

    # Include raw args/result JSON for receipts (bounded and deterministic).
    if step.args is not None:
        raw = _stable_json(step.args)
        capped, truncated = cap_text(raw, max_bytes=caps.max_preview_payload_bytes)
        body += "\n**Evidence: Args (JSON)**\n\n```json\n" + capped.rstrip("\n") + "\n```\n"
        if truncated:
            body += "_Args truncated._\n"

    if step.result is not None:
        raw = _stable_json(step.result)
        capped, truncated = cap_text(raw, max_bytes=caps.max_preview_payload_bytes)
        body += "\n**Evidence: Result (JSON)**\n\n```json\n" + capped.rstrip("\n") + "\n```\n"
        if truncated:
            body += "_Result truncated._\n"

    if step.preview is not None:
        preview_text, was_truncated = cap_text(
            step.preview.text, max_bytes=caps.max_preview_payload_bytes
        )
        truncated = bool(step.preview.truncated or was_truncated)

        body += "\n**Evidence: Preview**\n\n"
        body += "```text\n"
        body += preview_text.rstrip("\n")
        body += "\n```\n"
        if truncated:
            body += "_Preview truncated._\n"

    return header + body + "\n"


def compute_session_summary(*, steps: list[ObservedStep], casts_count: int) -> SessionSummary:
    tool_calls = sum(1 for s in steps if s.kind == "tool_call")
    queries = sum(1 for s in steps if (s.tool_category == "query" or s.name == "query"))
    blocks = sum(1 for s in steps if s.kind == "blocker")
    errors = sum(1 for s in steps if s.status == "error")
    warnings = sum(len(s.warnings or []) for s in steps)
    return SessionSummary(
        tool_calls=tool_calls,
        queries=queries,
        casts=casts_count,
        blocks=blocks,
        errors=errors,
        warnings=warnings,
    )


def _format_cast(*, c: Cast, caps: Caps) -> str:
    base = (
        f"### {c.title}\n\n"
        f"- Cast ID: `{c.id}`\n"
        f"- Kind: `{c.kind}`\n"
        f"- Created: `{c.created_at.isoformat()}`\n"
        f"- Evidence (origin_step_id): `{c.origin_step_id}`\n"
    )
    if c.origin_step_ids:
        base += (
            f"- Evidence (origin_step_ids): {', '.join(f'`{sid}`' for sid in c.origin_step_ids)}\n"
        )

    body = ""
    if isinstance(c, TableCast):
        sql, sql_truncated = cap_text(c.sql, max_bytes=caps.max_preview_payload_bytes)
        body += "\n**SQL**\n\n```sql\n" + sql.rstrip("\n") + "\n```\n"
        if sql_truncated:
            body += "_SQL truncated._\n"
        body += f"\n- Rows shown: {len(c.rows)}\n"
        if c.total_rows is not None:
            body += f"- Total rows: {c.total_rows}\n"
        if c.truncated:
            body += "- Table payload truncated (rows/cols) by caps.\n"

    return base + body + "\n"


def _stable_json(value: Any) -> str:
    import json

    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ": "), indent=2)
        + "\n"
    )
