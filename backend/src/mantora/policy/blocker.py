"""Blocker/pending-request models for Protective Mode approvals.

This module implements the minimal data model needed for a "human in the loop" approval flow
for risky operations (v0). It is intentionally simple and deterministic.

Per DEC-V0-SAFETY-MODES + PRI-PROTECTIVE-DEFAULT: protective mode is default.
Per DEC-V0-SESSIONS-CONVERSATION: blocker decisions are recorded as session steps.
Per PRI-HARD-CAPS-ALWAYS: payloads stored for UI/export should be capped where feasible.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class PendingDecision(str, Enum):
    allowed = "allowed"
    denied = "denied"
    timeout = "timeout"


class PendingStatus(str, Enum):
    pending = "pending"
    allowed = "allowed"
    denied = "denied"
    timeout = "timeout"


class PendingRequest(BaseModel):
    """A risky request that is awaiting a human allow/deny decision."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    session_id: UUID
    created_at: datetime

    tool_name: str = Field(min_length=1, max_length=200)
    arguments: JsonValue | None = None

    classification: str | None = None
    risk_level: str | None = None
    reason: str | None = None

    blocker_step_id: UUID | None = None

    status: PendingStatus = PendingStatus.pending
    decided_at: datetime | None = None


def blocker_summary(*, tool_name: str, decision: PendingDecision) -> str:
    if decision == PendingDecision.allowed:
        return f"Approved blocked {tool_name} request"
    if decision == PendingDecision.timeout:
        return f"Auto-denied blocked {tool_name} request (timeout)"
    return f"Denied blocked {tool_name} request"
