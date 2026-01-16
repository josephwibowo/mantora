from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response

from mantora.export import export_session_json, export_session_md
from mantora.models.events import (
    AddStepRequest,
    AddStepResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ObservedStep,
    Session,
    SessionSummary,
    TruncatedText,
)
from mantora.policy.truncation import cap_text
from mantora.store.interface import SessionStore

router = APIRouter(prefix="/api")


def _get_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.store)


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
    session = store.create_session(title=payload.title)
    return CreateSessionResponse(session=session)


@router.get("/sessions", response_model=list[Session])
def list_sessions(request: Request) -> list[Session]:
    store = _get_store(request)
    return list(store.list_sessions())


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: UUID, request: Request) -> Session:
    store = _get_store(request)
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


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


@router.post("/sessions/{session_id}/steps", response_model=AddStepResponse)
def add_step(session_id: UUID, payload: AddStepRequest, request: Request) -> AddStepResponse:
    store = _get_store(request)
    settings = request.app.state.settings

    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

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
        args=payload.args,
        result=payload.result,
        preview=preview,
    )

    try:
        store.add_step(step)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err

    return AddStepResponse(step=step)


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
