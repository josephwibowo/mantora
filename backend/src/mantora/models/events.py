from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class TruncatedText(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    truncated: bool


ConfigSource = Literal["cli", "env", "pinned", "roots", "ui", "git", "unknown"]


class SessionContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_root: str | None = Field(default=None, max_length=500)
    repo_name: str | None = Field(default=None, max_length=200)
    branch: str | None = Field(default=None, max_length=200)
    commit: str | None = Field(default=None, max_length=40)
    dirty: bool | None = None
    config_source: ConfigSource = "unknown"
    tag: str | None = Field(default=None, max_length=200)


class Session(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str | None
    created_at: datetime
    context: SessionContext | None = None


ObservedStepKind = Literal["tool_call", "tool_result", "note", "blocker", "blocker_decision"]
StepCategory = Literal["query", "schema", "list", "cast", "unknown"]
StepDecision = Literal["pending", "allowed", "denied", "timeout"]


class ObservedStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    session_id: UUID
    created_at: datetime

    kind: ObservedStepKind = "tool_call"
    name: str

    status: Literal["ok", "error"] = "ok"
    duration_ms: int | None = None

    # Optional "one-line" summary for UI display.
    summary: str | None = None
    # Optional risk level label for fast UI filtering (e.g., "LOW" / "MEDIUM" / "CRITICAL").
    risk_level: str | None = None
    # Optional list of warning labels (e.g., ["NO_LIMIT", "SELECT_STAR"])
    warnings: list[str] | None = None
    # Optional list of tables touched by this step (best-effort; may be partial).
    tables_touched: list[str] | None = None

    # Receipt/trace v1 normalized fields (all optional for backwards compatibility).
    target_type: str | None = None
    tool_category: StepCategory | None = None

    # SQL excerpt as captured by Mantora (capped). Only set when extractable.
    sql: TruncatedText | None = None
    sql_classification: str | None = None

    policy_rule_ids: list[str] | None = None
    decision: StepDecision | None = None

    result_rows_shown: int | None = None
    result_rows_total: int | None = None
    captured_bytes: int | None = None

    # Normalized DB error message (capped). Useful when the raw result is opaque.
    error_message: str | None = None

    args: JsonValue | None = None
    result: JsonValue | None = None

    preview: TruncatedText | None = None


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    tag: str | None = Field(default=None, max_length=200)


class CreateSessionResponse(BaseModel):
    session: Session


class AddStepRequest(BaseModel):
    kind: ObservedStepKind = "tool_call"
    name: str = Field(min_length=1, max_length=200)

    status: Literal["ok", "error"] = "ok"
    duration_ms: int | None = Field(default=None, ge=0)

    summary: str | None = Field(default=None, max_length=500)
    risk_level: str | None = Field(default=None, max_length=50)
    warnings: list[str] | None = Field(default=None)
    tables_touched: list[str] | None = Field(default=None)

    target_type: str | None = Field(default=None, max_length=50)
    tool_category: StepCategory | None = None

    sql_text: str | None = None
    sql_truncated: bool = False
    sql_classification: str | None = Field(default=None, max_length=50)

    policy_rule_ids: list[str] | None = None
    decision: StepDecision | None = None

    result_rows_shown: int | None = Field(default=None, ge=0)
    result_rows_total: int | None = Field(default=None, ge=0)
    captured_bytes: int | None = Field(default=None, ge=0)

    error_message: str | None = Field(default=None, max_length=2000)

    args: JsonValue | None = None
    result: JsonValue | None = None

    preview_text: str | None = None


class AddStepResponse(BaseModel):
    step: ObservedStep


class SessionSummary(BaseModel):
    """Computed summary counts for a session export."""

    model_config = ConfigDict(frozen=True)

    tool_calls: int
    queries: int
    casts: int
    blocks: int
    errors: int
    warnings: int
    duration_ms_total: int | None = None
    status: Literal["clean", "warnings", "blocked"] | None = None
    tables_touched: list[str] | None = None
