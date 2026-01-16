"""API routes for cast artifacts."""

from __future__ import annotations

from typing import Any
from typing import cast as typing_cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mantora.casts.models import Cast, TableCast
from mantora.store.interface import SessionStore

router = APIRouter(prefix="/api")


def _get_store(request: Request) -> SessionStore:
    return typing_cast(SessionStore, request.app.state.store)


class CastResponse(BaseModel):
    """Response model for a single cast."""

    id: str
    session_id: str
    created_at: str
    kind: str
    title: str
    origin_step_id: str
    origin_step_ids: list[str]

    # Table-specific
    sql: str | None = None
    rows: list[dict[str, Any]] | None = None
    total_rows: int | None = None

    truncated: bool = False


def _cast_to_response(c: Cast) -> CastResponse:
    """Convert a Cast model to API response."""
    origin_step_ids = [str(sid) for sid in c.origin_step_ids]

    if isinstance(c, TableCast):
        return CastResponse(
            id=str(c.id),
            session_id=str(c.session_id),
            created_at=c.created_at.isoformat(),
            kind=c.kind,
            title=c.title,
            origin_step_id=str(c.origin_step_id),
            origin_step_ids=origin_step_ids,
            sql=c.sql,
            rows=c.rows,
            total_rows=c.total_rows,
            truncated=c.truncated,
        )
    else:
        # Fallback for unsupported cast kinds
        return CastResponse(
            id=str(c.id),
            session_id=str(c.session_id),
            created_at=c.created_at.isoformat(),
            kind=c.kind,
            title=c.title,
            origin_step_id=str(c.origin_step_id),
            origin_step_ids=origin_step_ids,
        )


@router.get("/sessions/{session_id}/casts", response_model=list[CastResponse])
def list_casts(session_id: UUID, request: Request) -> list[CastResponse]:
    """List all casts for a session."""
    store = _get_store(request)
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    casts = store.list_casts(session_id)
    return [_cast_to_response(c) for c in casts]


@router.get("/casts/{cast_id}", response_model=CastResponse)
def get_cast(cast_id: UUID, request: Request) -> CastResponse:
    """Get a single cast by ID."""
    store = _get_store(request)
    c = store.get_cast(cast_id)
    if c is None:
        raise HTTPException(status_code=404, detail="cast not found")
    return _cast_to_response(c)
