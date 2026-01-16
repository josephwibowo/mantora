"""Adapter interface for normalizing target MCP tool calls.

Per DEC-V0-ADAPTERS-PER-TARGET: normalization via per-target adapters.
Per PAT-ADAPTER-INTERFACE: small deterministic adapter interface.
Per PRI-HARD-CAPS-ALWAYS: adapters must not create unbounded previews.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Protocol

from mantora.policy.truncation import cap_text

# Stable categories for tool interactions
StepCategory = Literal["query", "schema", "list", "cast", "session", "unknown"]

# Default preview cap (8KB)
DEFAULT_PREVIEW_CAP_BYTES = 8 * 1024


@dataclass(frozen=True)
class NormalizedStep:
    """Normalized representation of a tool interaction.

    This is the adapter's output, ready to be stored as an ObservedStep.
    """

    category: StepCategory
    tool_name: str
    status: Literal["ok", "error"]

    # Evidence fields (SQL, table name, etc.)
    evidence: dict[str, Any]

    # Capped preview for storage/UI
    preview_text: str
    preview_truncated: bool

    # Optional error message
    error_message: str | None = None


class Adapter(Protocol):
    """Protocol for target-specific adapters.

    Adapters normalize tool calls and results from specific MCP servers
    (DuckDB, Postgres, etc.) into a common format for observation.
    """

    @property
    def target_type(self) -> str:
        """Return the target type this adapter handles (e.g., 'duckdb', 'postgres')."""
        ...

    def categorize_tool(self, tool_name: str) -> StepCategory:
        """Categorize a tool by its name.

        Args:
            tool_name: The name of the tool being called.

        Returns:
            The category of the tool interaction.
        """
        ...

    def extract_evidence(
        self, tool_name: str, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract evidence fields from a tool call.

        Args:
            tool_name: The name of the tool.
            arguments: The arguments passed to the tool.
            result: The result from the tool (may be None for errors).

        Returns:
            Dictionary of evidence fields (sql, table, params, etc.).
        """
        ...

    def build_preview(
        self, tool_name: str, result: Any, *, max_bytes: int = DEFAULT_PREVIEW_CAP_BYTES
    ) -> tuple[str, bool]:
        """Build a capped preview from the tool result.

        Args:
            tool_name: The name of the tool.
            result: The result from the tool.
            max_bytes: Maximum bytes for the preview.

        Returns:
            Tuple of (preview_text, was_truncated).
        """
        ...

    def normalize(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        *,
        is_error: bool = False,
        error_message: str | None = None,
        max_preview_bytes: int = DEFAULT_PREVIEW_CAP_BYTES,
    ) -> NormalizedStep:
        """Normalize a complete tool interaction.

        This is the main entry point for adapters. It combines categorization,
        evidence extraction, and preview building into a single NormalizedStep.

        Args:
            tool_name: The name of the tool.
            arguments: The arguments passed to the tool.
            result: The result from the tool.
            is_error: Whether the call resulted in an error.
            error_message: Error message if is_error is True.
            max_preview_bytes: Maximum bytes for the preview.

        Returns:
            A NormalizedStep ready for storage.
        """
        ...


class BaseAdapter:
    """Base implementation with common adapter logic.

    Subclasses should override the tool mapping and evidence extraction
    for their specific target type.
    """

    # Tool name -> category mapping (override in subclasses)
    _tool_categories: ClassVar[dict[str, StepCategory]] = {}

    # Tool name aliases (override in subclasses)
    # Maps alternative names to canonical names
    _tool_aliases: ClassVar[dict[str, str]] = {}

    @property
    def target_type(self) -> str:
        raise NotImplementedError

    def _resolve_tool_name(self, tool_name: str) -> str:
        """Resolve tool name through aliases."""
        return self._tool_aliases.get(tool_name, tool_name)

    def categorize_tool(self, tool_name: str) -> StepCategory:
        resolved = self._resolve_tool_name(tool_name)
        return self._tool_categories.get(resolved, "unknown")

    def extract_evidence(
        self, tool_name: str, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Default evidence extraction. Override for specific fields."""
        evidence: dict[str, Any] = {}

        # Common patterns: look for SQL in arguments
        for key in ("sql", "query", "statement"):
            if key in arguments:
                evidence["sql"] = arguments[key]
                break

        # Look for table name
        for key in ("table", "table_name", "tableName"):
            if key in arguments:
                evidence["table"] = arguments[key]
                break

        return evidence

    def build_preview(
        self, tool_name: str, result: Any, *, max_bytes: int = DEFAULT_PREVIEW_CAP_BYTES
    ) -> tuple[str, bool]:
        """Build preview from result, respecting byte cap."""
        if result is None:
            return "", False

        # Handle MCP CallToolResult
        if hasattr(result, "content"):
            content = result.content
            if content and len(content) > 0:
                first = content[0]
                if hasattr(first, "text"):
                    return cap_text(first.text, max_bytes=max_bytes)

        # Handle string result
        if isinstance(result, str):
            return cap_text(result, max_bytes=max_bytes)

        # Handle dict/list - convert to string
        if isinstance(result, dict | list):
            import json

            text = json.dumps(result, indent=2, default=str)
            return cap_text(text, max_bytes=max_bytes)

        # Fallback
        return cap_text(str(result), max_bytes=max_bytes)

    def normalize(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        *,
        is_error: bool = False,
        error_message: str | None = None,
        max_preview_bytes: int = DEFAULT_PREVIEW_CAP_BYTES,
    ) -> NormalizedStep:
        category = self.categorize_tool(tool_name)
        evidence = self.extract_evidence(tool_name, arguments, result)
        preview_text, preview_truncated = self.build_preview(
            tool_name, result, max_bytes=max_preview_bytes
        )

        return NormalizedStep(
            category=category,
            tool_name=tool_name,
            status="error" if is_error else "ok",
            evidence=evidence,
            preview_text=preview_text,
            preview_truncated=preview_truncated,
            error_message=error_message if is_error else None,
        )
