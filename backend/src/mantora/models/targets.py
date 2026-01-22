"""Target configuration models for UI-based target management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Target(BaseModel):
    """A configured MCP target server."""

    id: UUID
    name: str = Field(..., description="User-friendly name for the target")
    type: str = Field(..., description="Target type (duckdb, postgres, etc.)")
    command: list[str] = Field(..., description="Command to execute the MCP server")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    is_active: bool = Field(default=False, description="Whether this is the active target")
    created_at: datetime
    updated_at: datetime
