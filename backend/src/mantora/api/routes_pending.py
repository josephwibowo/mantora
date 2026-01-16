from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from mantora.policy.blocker import PendingRequest, PendingStatus
from mantora.store.interface import SessionStore

router = APIRouter(prefix="/api")


def _get_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.store)


@router.post("/pending/{request_id}/allow", response_model=PendingRequest)
def allow_pending(request_id: UUID, request: Request) -> PendingRequest:
    store = _get_store(request)

    existing = store.get_pending_request(request_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="pending request not found")

    decided = store.decide_pending_request(request_id, status=PendingStatus.allowed)
    if decided is None:
        raise HTTPException(status_code=404, detail="pending request not found")

    return decided


@router.post("/pending/{request_id}/deny", response_model=PendingRequest)
def deny_pending(request_id: UUID, request: Request) -> PendingRequest:
    store = _get_store(request)

    existing = store.get_pending_request(request_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="pending request not found")

    decided = store.decide_pending_request(request_id, status=PendingStatus.denied)
    if decided is None:
        raise HTTPException(status_code=404, detail="pending request not found")

    return decided


@router.get("/sessions/{session_id}/pending", response_model=list[PendingRequest])
def list_pending(session_id: UUID, request: Request) -> list[PendingRequest]:
    """List pending requests for a session (primarily for UI hydration)."""
    store = _get_store(request)
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    # Only return still-pending items.
    return list(store.list_pending_requests(session_id, status=PendingStatus.pending))
