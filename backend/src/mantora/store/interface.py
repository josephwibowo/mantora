from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from mantora.casts.models import Cast
from mantora.models.events import ObservedStep, Session, SessionContext
from mantora.policy.blocker import PendingRequest, PendingStatus


class SessionStore(Protocol):
    def create_session(
        self,
        *,
        title: str | None,
        context: SessionContext | None = None,
        client_id: str | None = None,
    ) -> Session: ...

    def list_sessions(
        self,
        *,
        q: str | None = None,
        tag: str | None = None,
        repo_name: str | None = None,
        branch: str | None = None,
        since: datetime | None = None,
        has_warnings: bool | None = None,
        has_blocks: bool | None = None,
    ) -> Sequence[Session]: ...

    def get_session(self, session_id: UUID) -> Session | None: ...

    def update_session_tag(self, session_id: UUID, *, tag: str | None) -> Session | None: ...

    def update_session_context(
        self, session_id: UUID, *, context: SessionContext | None
    ) -> Session | None: ...

    def get_session_client_id(self, session_id: UUID) -> str | None: ...

    def get_client_default_repo_root(self, client_id: str) -> str | None: ...

    def set_client_default_repo_root(self, client_id: str, *, repo_root: str | None) -> None: ...

    def session_exists(self, session_id: UUID) -> bool:
        """Check if a session exists without fetching full session data.

        Returns True if session exists, False otherwise.
        """
        ...

    def get_last_active_at(self, session_id: UUID) -> datetime | None:
        """Get the timestamp of the last activity in a session.

        Activity is defined as the most recent step added to the session.
        Returns None if session doesn't exist or has no steps.
        """
        ...

    def delete_session(self, session_id: UUID) -> bool: ...

    def add_step(self, step: ObservedStep) -> None: ...

    def update_step(
        self,
        step_id: UUID,
        *,
        summary: str | None = None,
        status: str | None = None,
        args: dict[str, JsonValue] | None = None,
    ) -> bool:
        """Update an existing step's fields.

        Returns True if step was found and updated, False otherwise.
        """
        ...

    def list_steps(self, session_id: UUID) -> Sequence[ObservedStep]: ...

    def get_step_queue(self, session_id: UUID) -> asyncio.Queue[ObservedStep] | None: ...

    # Cast artifact methods
    def add_cast(self, cast: Cast) -> None: ...

    def list_casts(self, session_id: UUID) -> Sequence[Cast]: ...

    def get_cast(self, cast_id: UUID) -> Cast | None: ...

    # Pending request (blocker) methods
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
    ) -> PendingRequest: ...

    def get_pending_request(self, request_id: UUID) -> PendingRequest | None: ...

    def list_pending_requests(
        self, session_id: UUID, *, status: PendingStatus | None = None
    ) -> Sequence[PendingRequest]: ...

    def decide_pending_request(
        self, request_id: UUID, *, status: PendingStatus
    ) -> PendingRequest | None: ...
