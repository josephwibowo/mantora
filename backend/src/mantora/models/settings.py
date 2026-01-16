"""Settings and policy models for API exposure."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mantora.config.settings import Caps, SafetyMode


class PolicyRule(BaseModel):
    """A single policy rule that can be enforced."""

    id: str = Field(description="Unique rule identifier")
    label: str = Field(description="Human-readable rule name")
    description: str = Field(description="Detailed rule description")


class PolicyManifest(BaseModel):
    """Complete policy manifest exposed to clients."""

    safety_mode: SafetyMode = Field(description="Current safety mode")
    active_rules: list[PolicyRule] = Field(
        default_factory=list, description="List of currently active policy rules"
    )
    limits: Caps = Field(description="Resource limits and caps")
