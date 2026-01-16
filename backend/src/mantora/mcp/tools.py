"""Observer-native MCP tools for session lifecycle and casts.

Per DEC-V0-SESSIONS-CONVERSATION: sessions map to agent conversations.
Per DEC-V0-CASTS-EXPLICIT-TOOLS: casts are explicit observer-native tools.
Tools: session_start, session_end, session_current, cast_table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from mantora.casts.models import SchemaColumn, TableCast
from mantora.policy.caps import CapsConfig, cap_tabular_data
from mantora.store import SessionStore


class SessionTools:
    """Session lifecycle tools for the MCP proxy.

    Manages the current session state and provides tools for explicit
    session control. Falls back to auto-creating a session on first
    tool call if no session exists.

    Per-connection session isolation: each process/connection maintains
    its own session state to prevent cross-agent session bleed.
    """

    def __init__(
        self,
        store: SessionStore,
        *,
        connection_id: UUID | None = None,
        timeout_seconds: float = 1800.0,
    ) -> None:
        self._store = store
        self._connection_id: UUID = connection_id or uuid4()
        self._session_ids: dict[UUID, UUID] = {}
        self._timeout_seconds = timeout_seconds

    @property
    def current_session_id(self) -> UUID | None:
        """Get the current session ID for the default connection, if any."""
        return self._session_ids.get(self._connection_id)

    def _resolve_connection_id(self, connection_id: UUID | None) -> UUID:
        return connection_id or self._connection_id

    def session_start(self, title: str | None = None, *, connection_id: UUID | None = None) -> str:
        """Start a new session.

        Args:
            title: Optional title for the session.
            connection_id: Optional connection ID for per-connection isolation.

        Returns:
            The new session ID as a string.
        """
        session = self._store.create_session(title=title)
        resolved_connection_id = self._resolve_connection_id(connection_id)
        self._session_ids[resolved_connection_id] = session.id
        return str(session.id)

    def session_end(self, session_id: str, *, connection_id: UUID | None = None) -> bool:
        """End a session.

        Args:
            session_id: The session ID to end.
            connection_id: Optional connection ID for per-connection isolation.

        Returns:
            True if the session was ended, False if it wasn't the current session.
        """
        try:
            sid = UUID(session_id)
        except ValueError:
            return False

        resolved_connection_id = self._resolve_connection_id(connection_id)
        if self._session_ids.get(resolved_connection_id) == sid:
            self._session_ids.pop(resolved_connection_id, None)
            return True
        return False

    def session_current(self, *, connection_id: UUID | None = None) -> str | None:
        """Get the current session ID.

        Args:
            connection_id: Optional connection ID for per-connection isolation.

        Returns:
            The current session ID as a string, or None if no session is active.
        """
        resolved_connection_id = self._resolve_connection_id(connection_id)
        session_id = self._session_ids.get(resolved_connection_id)
        if session_id is None:
            return None
        return str(session_id)

    def ensure_session(self, *, connection_id: UUID | None = None) -> UUID:
        """Ensure a session exists, creating one if needed.

        This implements the fallback behavior: auto-create session on first
        tool call if no session exists.

        Validates that cached session still exists in the store to prevent
        stale session IDs from being reused (e.g., after session deletion).

        Also checks for session timeout: if the last activity is older than
        the configured timeout, a new session is created.

        Args:
            connection_id: Optional connection ID for per-connection isolation.

        Returns:
            The current session ID.
        """
        from datetime import UTC, datetime

        resolved_connection_id = self._resolve_connection_id(connection_id)
        session_id = self._session_ids.get(resolved_connection_id)

        # Validate cached session still exists in store
        if session_id is not None and not self._store.session_exists(session_id):
            # Session was deleted or doesn't exist, reset
            self._session_ids.pop(resolved_connection_id, None)
            session_id = None

        # Check for session timeout
        if session_id is not None and self._timeout_seconds > 0:
            last_active = self._store.get_last_active_at(session_id)
            if last_active is not None:
                elapsed = (datetime.now(UTC) - last_active).total_seconds()
                if elapsed > self._timeout_seconds:
                    # Session has timed out, create a new one
                    self._session_ids.pop(resolved_connection_id, None)
                    session_id = None

        # Create new session if needed
        if session_id is None:
            session = self._store.create_session(title=None)
            session_id = session.id
            self._session_ids[resolved_connection_id] = session_id
        return session_id


class CastTools:
    """Cast artifact tools for the MCP proxy.

    Per DEC-V0-CASTS-EXPLICIT-TOOLS: casts are explicit observer-native tools.
    Per PRI-EVIDENCE-LINKED: every cast links to evidence (originating step(s) + inputs).
    Per PRI-HARD-CAPS-ALWAYS: casts must be capped.
    """

    def __init__(self, store: SessionStore, session_tools: SessionTools) -> None:
        self._store = store
        self._session_tools = session_tools
        self._caps_config = CapsConfig()

    def cast_table(
        self,
        title: str,
        sql: str,
        rows: list[dict[str, Any]],
        *,
        origin_step_id: str | None = None,
        columns: list[dict[str, Any]] | None = None,
        connection_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create a table cast artifact.

        Args:
            title: Title for the table.
            sql: The SQL query that produced the data.
            rows: The data rows (list of dicts).
            origin_step_id: The step ID that originated this cast (for evidence linkage).
            columns: Optional column definitions (name, type).
            connection_id: Optional connection ID for per-connection isolation.

        Returns:
            Dict with cast_id and truncation info.
        """
        session_id = self._session_tools.ensure_session(connection_id=connection_id)
        step_id = UUID(origin_step_id) if origin_step_id else uuid4()

        # Infer columns if not provided
        final_columns: list[SchemaColumn] | None = None
        if columns:
            final_columns = [
                SchemaColumn(name=col["name"], type=col.get("type")) for col in columns
            ]
        elif rows:
            final_columns = _infer_columns(rows)

        # Apply caps per PRI-HARD-CAPS-ALWAYS
        capped = cap_tabular_data(
            rows,
            max_rows=self._caps_config.max_rows,
            max_columns=self._caps_config.max_columns,
        )

        cast_obj = TableCast(
            id=uuid4(),
            session_id=session_id,
            created_at=datetime.now(UTC),
            origin_step_id=step_id,
            title=title,
            sql=sql,
            rows=capped.data,
            columns=final_columns,
            total_rows=len(rows),
            truncated=capped.was_truncated,
        )

        self._store.add_cast(cast_obj)

        return {
            "cast_id": str(cast_obj.id),
            "rows_shown": len(capped.data),
            "total_rows": len(rows),
            "truncated": capped.was_truncated,
        }


def _infer_columns(rows: list[dict[str, Any]]) -> list[SchemaColumn]:
    """Infer columns from the first row of data.

    Args:
        rows: List of data rows.

    Returns:
        List of SchemaColumn objects with inferred types.
    """
    if not rows:
        return []

    first_row = rows[0]
    columns = []

    for name, value in first_row.items():
        col_type = "string"  # Default
        if isinstance(value, bool):
            col_type = "boolean"
        elif isinstance(value, int):
            col_type = "integer"
        elif isinstance(value, float):
            col_type = "float"
        elif value is None:
            col_type = "string"  # Assume string for nulls initially

        columns.append(SchemaColumn(name=name, type=col_type))

    return columns
