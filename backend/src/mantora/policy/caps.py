"""Caps enforcement for preview artifacts.

Per PRI-HARD-CAPS-ALWAYS: caps are enforced regardless of agent requests.
Per PIT-UNBOUNDED-PREVIEWS: must cap rows/bytes/cols.

Enforces hard limits on captured preview data before storage and streaming.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mantora.policy.truncation import cap_text


@dataclass(frozen=True)
class CapsConfig:
    """Configuration for preview caps."""

    max_rows: int = 200
    max_columns: int = 80
    max_bytes: int = 512 * 1024  # 512KB


@dataclass(frozen=True)
class CappedResult:
    """Result of applying caps to data."""

    data: Any
    rows_truncated: bool = False
    columns_truncated: bool = False
    bytes_truncated: bool = False

    @property
    def was_truncated(self) -> bool:
        """Whether any truncation occurred."""
        return self.rows_truncated or self.columns_truncated or self.bytes_truncated

    @property
    def truncation_summary(self) -> str | None:
        """Human-readable summary of truncations applied."""
        if not self.was_truncated:
            return None

        parts = []
        if self.rows_truncated:
            parts.append("rows")
        if self.columns_truncated:
            parts.append("columns")
        if self.bytes_truncated:
            parts.append("bytes")

        return f"Truncated: {', '.join(parts)}"


def cap_tabular_data(
    rows: list[dict[str, Any]],
    *,
    max_rows: int,
    max_columns: int,
) -> CappedResult:
    """Cap tabular data (list of dicts) by rows and columns.

    Args:
        rows: List of row dictionaries.
        max_rows: Maximum number of rows to keep.
        max_columns: Maximum number of columns to keep per row.

    Returns:
        CappedResult with truncated data and flags.
    """
    if not rows:
        return CappedResult(data=[])

    rows_truncated = len(rows) > max_rows
    capped_rows = rows[:max_rows]

    # Get column names from first row (assuming consistent schema)
    all_columns = list(capped_rows[0].keys()) if capped_rows else []
    columns_truncated = len(all_columns) > max_columns
    kept_columns = set(all_columns[:max_columns])

    # Filter columns if needed
    if columns_truncated:
        capped_rows = [{k: v for k, v in row.items() if k in kept_columns} for row in capped_rows]

    return CappedResult(
        data=capped_rows,
        rows_truncated=rows_truncated,
        columns_truncated=columns_truncated,
    )


def cap_text_preview(
    text: str,
    *,
    max_bytes: int,
) -> CappedResult:
    """Cap text preview by byte size.

    Args:
        text: The text to cap.
        max_bytes: Maximum bytes to keep.

    Returns:
        CappedResult with truncated text and flag.
    """
    capped, was_truncated = cap_text(text, max_bytes=max_bytes)
    return CappedResult(
        data=capped,
        bytes_truncated=was_truncated,
    )


def cap_preview(
    data: Any,
    *,
    config: CapsConfig | None = None,
) -> CappedResult:
    """Cap preview data based on its type.

    Handles:
    - str: byte cap
    - list[dict]: tabular row/column cap
    - Other: pass through (no capping)

    Args:
        data: The preview data to cap.
        config: Caps configuration (uses defaults if None).

    Returns:
        CappedResult with appropriately capped data.
    """
    if config is None:
        config = CapsConfig()

    # Text data
    if isinstance(data, str):
        return cap_text_preview(data, max_bytes=config.max_bytes)

    # Tabular data (list of dicts)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return cap_tabular_data(
            data,
            max_rows=config.max_rows,
            max_columns=config.max_columns,
        )

    # Unknown type - pass through
    return CappedResult(data=data)
