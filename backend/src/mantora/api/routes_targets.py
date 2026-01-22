"""API routes for target configuration management."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mantora.models.targets import Target
from mantora.store.interface import SessionStore

router = APIRouter(prefix="/api/targets", tags=["targets"])


def _get_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.store)


class CreateTargetRequest(BaseModel):
    """Request to create a new target."""

    name: str = Field(..., description="User-friendly name for the target")
    type: str = Field(..., description="Target type (duckdb, postgres, etc.)")
    command: list[str] = Field(..., description="Command to execute the MCP server")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")


class UpdateTargetRequest(BaseModel):
    """Request to update a target."""

    name: str | None = None
    type: str | None = None
    command: list[str] | None = None
    env: dict[str, str] | None = None


@router.post("", response_model=Target, status_code=201)
def create_target(req: CreateTargetRequest, request: Request) -> Target:
    """Create a new target configuration."""
    store = _get_store(request)
    target = store.create_target(
        name=req.name,
        type=req.type,
        command=req.command,
        env=req.env,
    )
    return target


@router.get("", response_model=list[Target])
def list_targets(request: Request) -> list[Target]:
    """List all configured targets."""
    store = _get_store(request)
    return list(store.list_targets())


@router.get("/active", response_model=Target | None)
def get_active_target(request: Request) -> Target | None:
    """Get the currently active target."""
    store = _get_store(request)
    return store.get_active_target()


@router.get("/{target_id}", response_model=Target)
def get_target(target_id: UUID, request: Request) -> Target:
    """Get a specific target by ID."""
    store = _get_store(request)
    target = store.get_target(target_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Target {target_id} not found")
    return target


@router.put("/{target_id}", response_model=Target)
def update_target(target_id: UUID, req: UpdateTargetRequest, request: Request) -> Target:
    """Update a target's configuration."""
    store = _get_store(request)
    target = store.update_target(
        target_id,
        name=req.name,
        type=req.type,
        command=req.command,
        env=req.env,
    )
    if target is None:
        raise HTTPException(status_code=404, detail=f"Target {target_id} not found")
    return target


@router.delete("/{target_id}", status_code=204)
def delete_target(target_id: UUID, request: Request) -> None:
    """Delete a target."""
    store = _get_store(request)
    deleted = store.delete_target(target_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Target {target_id} not found")


@router.post("/{target_id}/activate", response_model=Target)
def activate_target(target_id: UUID, request: Request) -> Target:
    """Set a target as active, deactivating all others."""
    store = _get_store(request)
    target = store.set_active_target(target_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Target {target_id} not found")
    return target
