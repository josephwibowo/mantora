"""Cast artifact models.

Per DEC-V0-CASTS-EXPLICIT-TOOLS: casts are explicit observer-native tools.
Per PRI-EVIDENCE-LINKED: every cast links to evidence (originating step(s) + inputs).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CastKind = Literal["table"]


class SchemaColumn(BaseModel):
    """Schema information for a table column."""

    model_config = ConfigDict(frozen=True)

    name: str
    type: str | None = None


class CastBase(BaseModel):
    """Base model for all cast artifacts."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    session_id: UUID
    created_at: datetime

    # Evidence linkage (required per PRI-EVIDENCE-LINKED)
    origin_step_id: UUID
    origin_step_ids: list[UUID] = Field(default_factory=list)

    title: str


class TableCast(CastBase):
    """Table cast artifact.

    Displays SQL query results as a table with preview rows.
    """

    kind: Literal["table"] = "table"
    sql: str
    rows: list[dict[str, Any]]
    total_rows: int | None = None
    truncated: bool = False
    columns: list[SchemaColumn] | None = None


# Union type for all casts
Cast = TableCast
