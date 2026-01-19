from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from mantora.context import ContextResolver
from mantora.export import export_session_json, export_session_md
from mantora.export.receipt import ReceiptResult, generate_pr_receipt
from mantora.models.events import (
    AddStepRequest,
    AddStepResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ObservedStep,
    Session,
    SessionContext,
    SessionSummary,
    TruncatedText,
)
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore

router = APIRouter(prefix="/api")


def _get_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.store)


def _normalize_tag(tag: str | None) -> str | None:
    if tag is None:
        return None
    cleaned = tag.strip()
    if not cleaned:
        return None
    capped, _ = cap_text(cleaned, max_bytes=200)
    return capped


class UpdateSessionRequest(BaseModel):
    tag: str | None = Field(default=None, max_length=200)


class UpdateSessionRepoRootRequest(BaseModel):
    repo_root: str | None = Field(default=None, max_length=2000)


def _compute_summary(steps: list[ObservedStep]) -> SessionSummary:
    """Compute summary statistics for a session.

    Args:
        steps: List of steps in the session.

    Returns:
        SessionSummary with aggregated counts.
    """
    tool_calls = 0
    queries = 0
    casts = 0
    blocks = 0
    errors = 0
    warnings_count = 0

    for step in steps:
        if step.kind == "tool_call":
            tool_calls += 1
            # Count queries and casts based on tool name
            if step.name == "query" or step.name == "cast_table":
                queries += 1
            if step.name in ("cast_table", "cast_chart", "cast_note"):
                casts += 1
        elif step.kind == "blocker":
            blocks += 1

        if step.status == "error":
            errors += 1

        if step.warnings:
            warnings_count += len(step.warnings)

    return SessionSummary(
        tool_calls=tool_calls,
        queries=queries,
        casts=casts,
        blocks=blocks,
        errors=errors,
        warnings=warnings_count,
    )


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    store = _get_store(request)
    normalized_tag = _normalize_tag(payload.tag)
    context = SessionContext(tag=normalized_tag) if normalized_tag is not None else None
    session = store.create_session(title=payload.title, context=context)
    return CreateSessionResponse(session=session)


@router.get("/sessions", response_model=list[Session])
def list_sessions(
    request: Request,
    q: str | None = None,
    tag: str | None = None,
    repo_name: str | None = None,
    branch: str | None = None,
    since: datetime | None = None,
    has_warnings: bool | None = None,
    has_blocks: bool | None = None,
) -> list[Session]:
    store = _get_store(request)
    return list(
        store.list_sessions(
            q=q,
            tag=tag,
            repo_name=repo_name,
            branch=branch,
            since=since,
            has_warnings=has_warnings,
            has_blocks=has_blocks,
        )
    )


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: UUID, request: Request) -> Session:
    store = _get_store(request)
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=Session)
def update_session(session_id: UUID, payload: UpdateSessionRequest, request: Request) -> Session:
    store = _get_store(request)
    normalized_tag = _normalize_tag(payload.tag)
    session = store.update_session_tag(session_id, tag=normalized_tag)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.put("/sessions/{session_id}/repo-root", response_model=Session)
def update_session_repo_root(
    session_id: UUID, payload: UpdateSessionRepoRootRequest, request: Request
) -> Session:
    store = _get_store(request)
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    client_id = store.get_session_client_id(session_id)
    if client_id is None:
        raise HTTPException(status_code=400, detail="session is not associated with an MCP client")

    existing_tag = session.context.tag if session.context else None

    raw = payload.repo_root.strip() if isinstance(payload.repo_root, str) else ""
    if not raw:
        store.set_client_default_repo_root(client_id, repo_root=None)
        updated_context = SessionContext(tag=existing_tag) if existing_tag else None
        updated = store.update_session_context(session_id, context=updated_context)
        if updated is None:
            raise HTTPException(status_code=404, detail="session not found")
        return updated

    resolved = ContextResolver().resolve(project_root=Path(raw), forced_source="ui")
    if resolved is None or resolved.repo_root is None:
        raise HTTPException(status_code=400, detail="repo_root is not a git repository")

    store.set_client_default_repo_root(client_id, repo_root=resolved.repo_root)

    merged = SessionContext(**resolved.model_dump(exclude={"tag"}), tag=existing_tag)
    updated = store.update_session_context(session_id, context=merged)
    if updated is None:
        raise HTTPException(status_code=404, detail="session not found")
    return updated


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: UUID, request: Request) -> None:
    store = _get_store(request)
    deleted = store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")


@router.get("/sessions/{session_id}/steps", response_model=list[ObservedStep])
def list_steps(session_id: UUID, request: Request) -> list[ObservedStep]:
    store = _get_store(request)
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    return list(store.list_steps(session_id))


@router.get("/sessions/{session_id}/summary", response_model=SessionSummary)
def get_session_summary(session_id: UUID, request: Request) -> SessionSummary:
    """Get aggregated summary counts for a session."""
    store = _get_store(request)
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    steps = list(store.list_steps(session_id))
    return _compute_summary(steps)


@router.get("/sessions/{session_id}/rollup", response_model=SessionSummary)
def get_session_rollup(session_id: UUID, request: Request) -> SessionSummary:
    """Get an enriched rollup for detail views (may perform heavier aggregation)."""
    store = _get_store(request)
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    steps = list(store.list_steps(session_id))
    summary = _compute_summary(steps)

    duration_ms_total = sum(s.duration_ms or 0 for s in steps)
    tables: set[str] = set()
    for step in steps:
        if step.tables_touched:
            tables.update(step.tables_touched)

    status: Literal["clean", "warnings", "blocked"]
    if summary.blocks > 0:
        status = "blocked"
    elif summary.warnings > 0:
        status = "warnings"
    else:
        status = "clean"

    payload = summary.model_dump()
    payload.update(
        {
            "duration_ms_total": duration_ms_total,
            "status": status,
            "tables_touched": sorted(tables),
        }
    )
    return SessionSummary(**payload)


@router.post("/sessions/{session_id}/steps", response_model=AddStepResponse)
def add_step(session_id: UUID, payload: AddStepRequest, request: Request) -> AddStepResponse:
    store = _get_store(request)
    settings = request.app.state.settings

    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    sql: TruncatedText | None = None
    if payload.sql_text is not None:
        capped, truncated = cap_text(payload.sql_text, max_bytes=8 * 1024)
        sql = TruncatedText(text=capped, truncated=bool(payload.sql_truncated or truncated))

    preview: TruncatedText | None = None
    if payload.preview_text is not None:
        capped, truncated = cap_text(
            payload.preview_text,
            max_bytes=settings.caps.max_preview_payload_bytes,
        )
        preview = TruncatedText(text=capped, truncated=truncated)

    step = ObservedStep(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        kind=payload.kind,
        name=payload.name,
        status=payload.status,
        duration_ms=payload.duration_ms,
        summary=payload.summary,
        risk_level=payload.risk_level,
        warnings=payload.warnings,
        tables_touched=payload.tables_touched,
        target_type=payload.target_type,
        tool_category=payload.tool_category,
        sql=sql,
        sql_classification=payload.sql_classification,
        policy_rule_ids=payload.policy_rule_ids,
        decision=payload.decision,
        result_rows_shown=payload.result_rows_shown,
        result_rows_total=payload.result_rows_total,
        captured_bytes=payload.captured_bytes,
        error_message=payload.error_message,
        args=payload.args,
        result=payload.result,
        preview=preview,
    )

    try:
        store.add_step(step)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err

    return AddStepResponse(step=step)


class ReceiptRequest(BaseModel):
    include_data: bool = Field(default=False, description="Include sample data in the receipt")


@router.post("/sessions/{session_id}/receipt", response_model=ReceiptResult)
def post_session_receipt(
    session_id: UUID, payload: ReceiptRequest, request: Request
) -> ReceiptResult:
    store = _get_store(request)
    settings = request.app.state.settings

    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    return generate_pr_receipt(
        store=store,
        session_id=session_id,
        caps=settings.caps,
        include_data=payload.include_data,
    )


@router.get("/sessions/{session_id}/export.json")
def get_session_export_json(session_id: UUID, request: Request) -> Response:
    store = _get_store(request)
    settings = request.app.state.settings

    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    content = export_session_json(store=store, session_id=session_id, caps=settings.caps)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.json"'},
    )


@router.get("/sessions/{session_id}/export.md")
def get_session_export_md(session_id: UUID, request: Request) -> Response:
    store = _get_store(request)
    settings = request.app.state.settings

    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    content = export_session_md(store=store, session_id=session_id, caps=settings.caps)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.md"'},
    )
