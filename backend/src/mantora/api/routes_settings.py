"""Settings API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from mantora.config.settings import PolicyConfig
from mantora.models.settings import PolicyManifest, PolicyRule

router = APIRouter(prefix="/api", tags=["settings"])


def _get_active_rules(policy: PolicyConfig) -> list[PolicyRule]:
    """Derive active policy rules from policy config."""
    if not policy.protective_mode:
        return []

    rules: list[PolicyRule] = []
    if policy.block_ddl:
        rules.append(
            PolicyRule(
                id="block_ddl",
                label="Block DDL",
                description="Blocks CREATE, ALTER, DROP operations",
            )
        )
    if policy.block_dml:
        rules.append(
            PolicyRule(
                id="block_dml",
                label="Block DML",
                description="Blocks INSERT, UPDATE, DELETE operations",
            )
        )
    if policy.block_multi_statement:
        rules.append(
            PolicyRule(
                id="block_multi_statement",
                label="Block Multi-Statement",
                description="Blocks queries containing multiple SQL statements",
            )
        )
    if policy.block_delete_without_where:
        rules.append(
            PolicyRule(
                id="block_delete_without_where",
                label="Block DELETE without WHERE",
                description="Blocks DELETE statements that lack a WHERE clause",
            )
        )
    return rules


@router.get("/settings")
def get_settings(request: Request) -> PolicyManifest:
    """Get current settings and policy manifest.

    Returns:
        PolicyManifest with safety mode, active rules, and limits.
    """
    settings = request.app.state.settings

    return PolicyManifest(
        safety_mode=settings.safety_mode,
        active_rules=_get_active_rules(settings.policy),
        limits=settings.caps,
    )
