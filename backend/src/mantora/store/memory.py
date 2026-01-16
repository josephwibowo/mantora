from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import JsonValue

from mantora.casts.models import Cast
from mantora.models.events import ObservedStep, Session
from mantora.policy.blocker import PendingRequest, PendingStatus
from mantora.store.interface import SessionStore


class MemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}
        self._steps: dict[UUID, list[ObservedStep]] = {}
        self._queues: dict[UUID, asyncio.Queue[ObservedStep]] = {}
        self._casts: dict[UUID, Cast] = {}  # cast_id -> Cast
        self._session_casts: dict[UUID, list[UUID]] = {}  # session_id -> cast_ids
        self._pending: dict[UUID, PendingRequest] = {}  # request_id -> PendingRequest

    def create_session(self, *, title: str | None) -> Session:
        session_id = uuid4()
        session = Session(id=session_id, title=title, created_at=datetime.now(UTC))
        self._sessions[session_id] = session
        self._steps[session_id] = []
        self._queues[session_id] = asyncio.Queue()
        self._session_casts[session_id] = []
        return session

    def list_sessions(self) -> Sequence[Session]:
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def get_session(self, session_id: UUID) -> Session | None:
        return self._sessions.get(session_id)

    def session_exists(self, session_id: UUID) -> bool:
        """Check if a session exists without fetching full session data."""
        return session_id in self._sessions

    def get_last_active_at(self, session_id: UUID) -> datetime | None:
        """Get the timestamp of the last activity in a session."""
        if session_id not in self._sessions:
            return None

        steps = self._steps.get(session_id, [])
        if not steps:
            return None

        # Return the most recent step timestamp
        return max(step.created_at for step in steps)

    def delete_session(self, session_id: UUID) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            if session_id in self._steps:
                del self._steps[session_id]
            if session_id in self._queues:
                del self._queues[session_id]

            # Clean up casts
            cast_ids = self._session_casts.get(session_id, [])
            for cid in cast_ids:
                if cid in self._casts:
                    del self._casts[cid]
            if session_id in self._session_casts:
                del self._session_casts[session_id]

            # Clean up pending requests
            pending_ids = [p.id for p in self._pending.values() if p.session_id == session_id]
            for pid in pending_ids:
                del self._pending[pid]

            return True
        return False

    def add_step(self, step: ObservedStep) -> None:
        if step.session_id not in self._sessions:
            raise KeyError(step.session_id)

        self._steps[step.session_id].append(step)
        self._queues[step.session_id].put_nowait(step)

    def update_step(
        self,
        step_id: UUID,
        *,
        summary: str | None = None,
        status: str | None = None,
        args: dict[str, JsonValue] | None = None,
    ) -> bool:
        """Update an existing step's fields."""
        for session_id, steps in self._steps.items():
            for i, step in enumerate(steps):
                if step.id == step_id:
                    # Create updated step
                    step_args = step.args if isinstance(step.args, dict) else {}
                    updated_args = {**step_args, **(args or {})}
                    updated_status = status if status is not None else step.status
                    # Validate status is a valid literal
                    if updated_status not in ("ok", "error"):
                        return False
                    updated_step = ObservedStep(
                        **step.model_dump(exclude={"summary", "status", "args"}),
                        summary=summary if summary is not None else step.summary,
                        status=updated_status,  # type: ignore
                        args=updated_args,
                    )
                    self._steps[session_id][i] = updated_step
                    # Notify via queue
                    self._queues[session_id].put_nowait(updated_step)
                    return True
        return False

    def list_steps(self, session_id: UUID) -> Sequence[ObservedStep]:
        return list(self._steps.get(session_id, []))

    def get_step_queue(self, session_id: UUID) -> asyncio.Queue[ObservedStep] | None:
        return self._queues.get(session_id)

    def add_cast(self, cast: Cast) -> None:
        if cast.session_id not in self._sessions:
            raise KeyError(cast.session_id)

        self._casts[cast.id] = cast
        self._session_casts[cast.session_id].append(cast.id)

    def list_casts(self, session_id: UUID) -> Sequence[Cast]:
        cast_ids = self._session_casts.get(session_id, [])
        return [self._casts[cid] for cid in cast_ids if cid in self._casts]

    def get_cast(self, cast_id: UUID) -> Cast | None:
        return self._casts.get(cast_id)

    def create_pending_request(
        self,
        *,
        request_id: UUID | None = None,
        session_id: UUID,
        tool_name: str,
        arguments: JsonValue | None,
        classification: str | None,
        risk_level: str | None,
        reason: str | None,
        blocker_step_id: UUID | None,
    ) -> PendingRequest:
        from datetime import UTC, datetime
        from uuid import uuid4

        if session_id not in self._sessions:
            raise KeyError(session_id)

        req_id = request_id or uuid4()
        req = PendingRequest(
            id=req_id,
            session_id=session_id,
            created_at=datetime.now(UTC),
            tool_name=tool_name,
            arguments=arguments,
            classification=classification,
            risk_level=risk_level,
            reason=reason,
            blocker_step_id=blocker_step_id,
            status=PendingStatus.pending,
            decided_at=None,
        )
        self._pending[req.id] = req
        return req

    def get_pending_request(self, request_id: UUID) -> PendingRequest | None:
        return self._pending.get(request_id)

    def list_pending_requests(
        self, session_id: UUID, *, status: PendingStatus | None = None
    ) -> Sequence[PendingRequest]:
        items = [p for p in self._pending.values() if p.session_id == session_id]
        if status is not None:
            items = [p for p in items if p.status == status]
        return sorted(items, key=lambda p: p.created_at)

    def decide_pending_request(
        self, request_id: UUID, *, status: PendingStatus
    ) -> PendingRequest | None:
        from datetime import UTC, datetime

        existing = self._pending.get(request_id)
        if existing is None:
            return None
        decided = PendingRequest(
            **existing.model_dump(exclude={"status", "decided_at"}),
            status=status,
            decided_at=datetime.now(UTC),
        )
        self._pending[request_id] = decided
        return decided
