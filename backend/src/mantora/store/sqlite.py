from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from pydantic import JsonValue

from mantora.casts.models import Cast, TableCast
from mantora.config.settings import LimitsConfig
from mantora.models.events import (
    ConfigSource,
    ObservedStep,
    ObservedStepKind,
    Session,
    SessionContext,
    TruncatedText,
)
from mantora.policy.blocker import PendingRequest, PendingStatus
from mantora.store.interface import SessionStore
from mantora.store.retention import prune_sqlite_sessions


def _connect(db_path: Path) -> sqlite3.Connection:
    # isolation_level=None puts sqlite3 in autocommit mode
    # timeout=30.0 allows waiting for locks (essential for DELETE mode contention)
    conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    conn.execute("PRAGMA wal_autocheckpoint = 1000")  # Auto-checkpoint every 1000 pages
    conn.execute("PRAGMA busy_timeout = 30000")  # 30 second busy timeout
    return conn


class SQLiteSessionStore(SessionStore):
    def __init__(
        self,
        db_path: Path,
        *,
        retention_days: int | None = None,
        max_db_bytes: int | None = None,
    ) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = _connect(self._db_path)
        self._lock = threading.Lock()
        self._prune_lock = threading.Lock()

        self._queues: dict[UUID, asyncio.Queue[ObservedStep]] = {}

        limits = LimitsConfig()
        self._retention_days = limits.retention_days if retention_days is None else retention_days
        self._max_db_bytes = limits.max_db_bytes if max_db_bytes is None else max_db_bytes
        self._step_count = 0

        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    client_id TEXT,
                    repo_root TEXT,
                    repo_name TEXT,
                    branch_name TEXT,
                    commit_sha TEXT,
                    is_dirty INTEGER,
                    config_source TEXT,
                    tag TEXT
                )
                """
            )

            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_defaults (
                    client_id TEXT PRIMARY KEY,
                    repo_root TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms INTEGER,
                    summary_text TEXT,
                    risk_level TEXT,
                    warnings_json TEXT,
                    target_type TEXT,
                    tool_category TEXT,
                    sql_text TEXT,
                    sql_truncated INTEGER,
                    sql_classification TEXT,
                    policy_rule_ids_json TEXT,
                    decision TEXT,
                    result_rows_shown INTEGER,
                    result_rows_total INTEGER,
                    captured_bytes INTEGER,
                    error_message TEXT,
                    tables_touched_json TEXT,
                    args_json TEXT,
                    result_json TEXT,
                    preview_text TEXT,
                    preview_truncated INTEGER
                )
                """
            )

            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at)"
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_steps_session_created_at
                ON steps(session_id, created_at)
                """
            )

            # Casts table
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS casts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    origin_step_id TEXT NOT NULL,
                    origin_step_ids_json TEXT,
                    sql TEXT,
                    rows_json TEXT,
                    total_rows INTEGER,
                    vega_lite_spec_json TEXT,
                    data_json TEXT,
                    markdown TEXT,
                    truncated INTEGER
                )
                """
            )

            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_casts_session_created_at
                ON casts(session_id, created_at)
                """
            )

            # Pending requests table (blocker approvals)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_requests (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT,
                    classification TEXT,
                    risk_level TEXT,
                    reason TEXT,
                    blocker_step_id TEXT,
                    status TEXT NOT NULL,
                    decided_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pending_session_created_at
                ON pending_requests(session_id, created_at)
                """
            )

            # Lightweight migrations for older DBs (add columns if missing)
            session_cols = {
                row["name"] for row in self._conn.execute("PRAGMA table_info(sessions)")
            }
            if "client_id" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN client_id TEXT")
            if "repo_root" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN repo_root TEXT")
            if "repo_name" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN repo_name TEXT")
            if "branch_name" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN branch_name TEXT")
            if "commit_sha" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN commit_sha TEXT")
            if "is_dirty" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN is_dirty INTEGER")
            if "config_source" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN config_source TEXT")
            if "tag" not in session_cols:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN tag TEXT")

            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_branch ON sessions(branch_name)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_repo ON sessions(repo_name)"
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_tag ON sessions(tag)")

            # Lightweight migrations for older DBs (add columns if missing)
            step_cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(steps)")}
            if "summary_text" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN summary_text TEXT")
            if "risk_level" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN risk_level TEXT")
            if "warnings_json" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN warnings_json TEXT")
            if "target_type" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN target_type TEXT")
            if "tool_category" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN tool_category TEXT")
            if "sql_text" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN sql_text TEXT")
            if "sql_truncated" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN sql_truncated INTEGER")
            if "sql_classification" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN sql_classification TEXT")
            if "policy_rule_ids_json" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN policy_rule_ids_json TEXT")
            if "decision" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN decision TEXT")
            if "result_rows_shown" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN result_rows_shown INTEGER")
            if "result_rows_total" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN result_rows_total INTEGER")
            if "captured_bytes" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN captured_bytes INTEGER")
            if "error_message" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN error_message TEXT")
            if "tables_touched_json" not in step_cols:
                self._conn.execute("ALTER TABLE steps ADD COLUMN tables_touched_json TEXT")
        self._checkpoint()

    def _checkpoint(self) -> None:
        """Force a WAL checkpoint to ensure data is visible to the Docker app."""
        with self._lock, suppress(Exception):
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def _schedule_prune(self) -> None:
        if self._retention_days <= 0 and self._max_db_bytes <= 0:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.call_soon_threadsafe(self._maybe_prune)
        else:
            self._maybe_prune()

    def _maybe_prune(self) -> None:
        if self._retention_days <= 0 and self._max_db_bytes <= 0:
            return
        if not self._prune_lock.acquire(blocking=False):
            return
        try:
            prune_sqlite_sessions(
                db_path=self._db_path,
                retention_days=self._retention_days,
                max_db_bytes=self._max_db_bytes,
            )
        finally:
            self._prune_lock.release()

    def create_session(
        self,
        *,
        title: str | None,
        context: SessionContext | None = None,
        client_id: str | None = None,
    ) -> Session:
        session_id = uuid4()
        created_at = datetime.now(UTC)

        repo_root = context.repo_root if context else None
        repo_name = context.repo_name if context else None
        branch_name = context.branch if context else None
        commit_sha = context.commit if context else None
        is_dirty = (1 if context.dirty else 0) if (context and context.dirty is not None) else None
        config_source = context.config_source if context else None
        tag = context.tag if context else None

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sessions (
                    id,
                    title,
                    created_at,
                    client_id,
                    repo_root,
                    repo_name,
                    branch_name,
                    commit_sha,
                    is_dirty,
                    config_source,
                    tag
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """.strip(),
                (
                    str(session_id),
                    title,
                    created_at.isoformat(),
                    client_id,
                    repo_root,
                    repo_name,
                    branch_name,
                    commit_sha,
                    is_dirty,
                    config_source,
                    tag,
                ),
            )
        self._checkpoint()

        session = Session(id=session_id, title=title, created_at=created_at, context=context)
        self._queues[session_id] = asyncio.Queue()
        return session

    def list_sessions(
        self,
        *,
        q: str | None = None,
        tag: str | None = None,
        repo_name: str | None = None,
        branch: str | None = None,
        since: datetime | None = None,
        has_warnings: bool | None = None,
        has_blocks: bool | None = None,
    ) -> Sequence[Session]:
        # Create a fresh connection for read operations to ensure WAL visibility
        conn = _connect(self._db_path)
        try:
            where: list[str] = []
            params: list[object] = []

            if tag is not None:
                where.append("tag = ?")
                params.append(tag)
            if repo_name is not None:
                where.append("repo_name = ?")
                params.append(repo_name)
            if branch is not None:
                where.append("branch_name = ?")
                params.append(branch)
            if since is not None:
                where.append("created_at >= ?")
                params.append(since.isoformat())

            if has_warnings is not None:
                clause = (
                    "EXISTS (SELECT 1 FROM steps WHERE steps.session_id = sessions.id "
                    "AND warnings_json IS NOT NULL AND warnings_json != '[]')"
                )
                where.append(clause if has_warnings else f"NOT {clause}")

            if has_blocks is not None:
                clause = (
                    "EXISTS (SELECT 1 FROM steps WHERE steps.session_id = sessions.id "
                    "AND kind = 'blocker')"
                )
                where.append(clause if has_blocks else f"NOT {clause}")

            if q is not None and q.strip():
                needle = f"%{q.strip().lower()}%"
                where.append(
                    "("
                    "LOWER(COALESCE(title, '')) LIKE ? OR "
                    "LOWER(COALESCE(repo_name, '')) LIKE ? OR "
                    "LOWER(COALESCE(branch_name, '')) LIKE ? OR "
                    "LOWER(COALESCE(tag, '')) LIKE ?"
                    ")"
                )
                params.extend([needle, needle, needle, needle])

            where_sql = f"WHERE {' AND '.join(where)}" if where else ""

            with self._lock:
                rows = conn.execute(
                    f"""
                    SELECT
                        id,
                        title,
                        created_at,
                        repo_root,
                        repo_name,
                        branch_name,
                        commit_sha,
                        is_dirty,
                        config_source,
                        tag
                    FROM sessions
                    {where_sql}
                    ORDER BY created_at DESC
                    """.strip(),
                    params,
                ).fetchall()

            sessions: list[Session] = []
            for row in rows:
                context: SessionContext | None = None
                if any(
                    row[k] is not None
                    for k in (
                        "repo_root",
                        "repo_name",
                        "branch_name",
                        "commit_sha",
                        "is_dirty",
                        "config_source",
                        "tag",
                    )
                ):
                    raw_source = row["config_source"]
                    config_source: ConfigSource
                    if isinstance(raw_source, str) and raw_source in (
                        "cli",
                        "env",
                        "pinned",
                        "roots",
                        "ui",
                        "git",
                        "unknown",
                    ):
                        config_source = cast(ConfigSource, raw_source)
                    else:
                        config_source = "unknown"
                    context = SessionContext(
                        repo_root=row["repo_root"],
                        repo_name=row["repo_name"],
                        branch=row["branch_name"],
                        commit=row["commit_sha"],
                        dirty=(bool(row["is_dirty"]) if row["is_dirty"] is not None else None),
                        config_source=config_source,
                        tag=row["tag"],
                    )
                sessions.append(
                    Session(
                        id=UUID(row["id"]),
                        title=row["title"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        context=context,
                    )
                )
            return sessions
        finally:
            conn.close()

    def get_session(self, session_id: UUID) -> Session | None:
        # Create a fresh connection for read operations to ensure WAL visibility
        conn = _connect(self._db_path)
        try:
            with self._lock:
                row = conn.execute(
                    """
                    SELECT
                        id,
                        title,
                        created_at,
                        repo_root,
                        repo_name,
                        branch_name,
                        commit_sha,
                        is_dirty,
                        config_source,
                        tag
                    FROM sessions
                    WHERE id = ?
                    """.strip(),
                    (str(session_id),),
                ).fetchone()

            if row is None:
                return None

            context: SessionContext | None = None
            if any(
                row[k] is not None
                for k in (
                    "repo_root",
                    "repo_name",
                    "branch_name",
                    "commit_sha",
                    "is_dirty",
                    "config_source",
                    "tag",
                )
            ):
                raw_source = row["config_source"]
                config_source: ConfigSource
                if isinstance(raw_source, str) and raw_source in (
                    "cli",
                    "env",
                    "pinned",
                    "roots",
                    "ui",
                    "git",
                    "unknown",
                ):
                    config_source = cast(ConfigSource, raw_source)
                else:
                    config_source = "unknown"
                context = SessionContext(
                    repo_root=row["repo_root"],
                    repo_name=row["repo_name"],
                    branch=row["branch_name"],
                    commit=row["commit_sha"],
                    dirty=(bool(row["is_dirty"]) if row["is_dirty"] is not None else None),
                    config_source=config_source,
                    tag=row["tag"],
                )

            return Session(
                id=UUID(row["id"]),
                title=row["title"],
                created_at=datetime.fromisoformat(row["created_at"]),
                context=context,
            )
        finally:
            conn.close()

    def update_session_tag(self, session_id: UUID, *, tag: str | None) -> Session | None:
        with self._lock:
            result = self._conn.execute(
                "UPDATE sessions SET tag = ? WHERE id = ?",
                (tag, str(session_id)),
            )
            if result.rowcount == 0:
                return None
        self._checkpoint()
        return self.get_session(session_id)

    def update_session_context(
        self, session_id: UUID, *, context: SessionContext | None
    ) -> Session | None:
        repo_root = context.repo_root if context else None
        repo_name = context.repo_name if context else None
        branch_name = context.branch if context else None
        commit_sha = context.commit if context else None
        is_dirty = (1 if context.dirty else 0) if (context and context.dirty is not None) else None
        config_source = context.config_source if context else None
        tag = context.tag if context else None

        with self._lock:
            result = self._conn.execute(
                """
                UPDATE sessions
                SET
                    repo_root = ?,
                    repo_name = ?,
                    branch_name = ?,
                    commit_sha = ?,
                    is_dirty = ?,
                    config_source = ?,
                    tag = ?
                WHERE id = ?
                """.strip(),
                (
                    repo_root,
                    repo_name,
                    branch_name,
                    commit_sha,
                    is_dirty,
                    config_source,
                    tag,
                    str(session_id),
                ),
            )
            if result.rowcount == 0:
                return None
        self._checkpoint()
        return self.get_session(session_id)

    def get_session_client_id(self, session_id: UUID) -> str | None:
        conn = _connect(self._db_path)
        try:
            with self._lock:
                row = conn.execute(
                    "SELECT client_id FROM sessions WHERE id = ?",
                    (str(session_id),),
                ).fetchone()
            if row is None:
                return None
            raw = row["client_id"]
            return raw if isinstance(raw, str) and raw.strip() else None
        finally:
            conn.close()

    def get_client_default_repo_root(self, client_id: str) -> str | None:
        conn = _connect(self._db_path)
        try:
            with self._lock:
                row = conn.execute(
                    "SELECT repo_root FROM client_defaults WHERE client_id = ?",
                    (client_id,),
                ).fetchone()
            if row is None:
                return None
            raw = row["repo_root"]
            return raw if isinstance(raw, str) and raw.strip() else None
        finally:
            conn.close()

    def set_client_default_repo_root(self, client_id: str, *, repo_root: str | None) -> None:
        now = datetime.now(UTC).isoformat()
        cleaned = repo_root.strip() if isinstance(repo_root, str) else ""
        persisted = cleaned if cleaned else None

        with self._lock:
            if persisted is None:
                self._conn.execute(
                    "DELETE FROM client_defaults WHERE client_id = ?",
                    (client_id,),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO client_defaults (client_id, repo_root, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(client_id) DO UPDATE SET
                        repo_root = excluded.repo_root,
                        updated_at = excluded.updated_at
                    """.strip(),
                    (client_id, persisted, now),
                )
        self._checkpoint()

    def session_exists(self, session_id: UUID) -> bool:
        """Check if a session exists without fetching full session data."""
        conn = _connect(self._db_path)
        try:
            with self._lock:
                row = conn.execute(
                    "SELECT 1 FROM sessions WHERE id = ?",
                    (str(session_id),),
                ).fetchone()
            return row is not None
        finally:
            conn.close()

    def get_last_active_at(self, session_id: UUID) -> datetime | None:
        """Get the timestamp of the last activity in a session."""
        conn = _connect(self._db_path)
        try:
            with self._lock:
                # Check if session exists
                session_row = conn.execute(
                    "SELECT 1 FROM sessions WHERE id = ?",
                    (str(session_id),),
                ).fetchone()
                if session_row is None:
                    return None

                # Get the most recent step timestamp
                step_row = conn.execute(
                    "SELECT MAX(created_at) as last_active FROM steps WHERE session_id = ?",
                    (str(session_id),),
                ).fetchone()

                if step_row is None or step_row["last_active"] is None:
                    return None

                return datetime.fromisoformat(step_row["last_active"])
        finally:
            conn.close()

    def delete_session(self, session_id: UUID) -> bool:
        """Delete a session and all related data (steps, casts, pending_requests).

        Returns True if the session was deleted, False if it didn't exist.
        """
        with self._lock:
            # Check if session exists first
            exists = self._conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?",
                (str(session_id),),
            ).fetchone()
            if exists is None:
                return False

            # Delete session (CASCADE will handle steps, casts, pending_requests)
            self._conn.execute(
                "DELETE FROM sessions WHERE id = ?",
                (str(session_id),),
            )

        # Clean up in-memory queue if present
        self._queues.pop(session_id, None)
        self._checkpoint()
        return True

    def add_step(self, step: ObservedStep) -> None:
        warnings_json = (
            json.dumps(step.warnings, separators=(",", ":")) if step.warnings is not None else None
        )
        tables_touched_json = (
            json.dumps(step.tables_touched, separators=(",", ":"))
            if step.tables_touched is not None
            else None
        )
        policy_rule_ids_json = (
            json.dumps(step.policy_rule_ids, separators=(",", ":"))
            if step.policy_rule_ids is not None
            else None
        )
        args_json = json.dumps(step.args, separators=(",", ":")) if step.args is not None else None
        result_json = (
            json.dumps(step.result, separators=(",", ":")) if step.result is not None else None
        )

        sql_text: str | None
        sql_truncated: int | None
        if step.sql is None:
            sql_text = None
            sql_truncated = None
        else:
            sql_text = step.sql.text
            sql_truncated = 1 if step.sql.truncated else 0

        preview_text: str | None
        preview_truncated: int | None
        if step.preview is None:
            preview_text = None
            preview_truncated = None
        else:
            preview_text = step.preview.text
            preview_truncated = 1 if step.preview.truncated else 0

        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?",
                (str(step.session_id),),
            ).fetchone()
            if exists is None:
                raise KeyError(step.session_id)

            self._conn.execute(
                """
                INSERT INTO steps (
                    id,
                    session_id,
                    created_at,
                    kind,
                    name,
                    status,
                    duration_ms,
                    summary_text,
                    risk_level,
                    warnings_json,
                    target_type,
                    tool_category,
                    sql_text,
                    sql_truncated,
                    sql_classification,
                    policy_rule_ids_json,
                    decision,
                    result_rows_shown,
                    result_rows_total,
                    captured_bytes,
                    error_message,
                    tables_touched_json,
                    args_json,
                    result_json,
                    preview_text,
                    preview_truncated
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """.strip(),
                (
                    str(step.id),
                    str(step.session_id),
                    step.created_at.isoformat(),
                    step.kind,
                    step.name,
                    step.status,
                    step.duration_ms,
                    step.summary,
                    step.risk_level,
                    warnings_json,
                    step.target_type,
                    step.tool_category,
                    sql_text,
                    sql_truncated,
                    step.sql_classification,
                    policy_rule_ids_json,
                    step.decision,
                    step.result_rows_shown,
                    step.result_rows_total,
                    step.captured_bytes,
                    step.error_message,
                    tables_touched_json,
                    args_json,
                    result_json,
                    preview_text,
                    preview_truncated,
                ),
            )
            self._step_count += 1
            should_prune = self._step_count % 100 == 0
        self._checkpoint()

        queue = self._queues.get(step.session_id)
        if queue is None:
            queue = asyncio.Queue()
            self._queues[step.session_id] = queue
        queue.put_nowait(step)
        if should_prune:
            self._schedule_prune()

    def update_step(
        self,
        step_id: UUID,
        *,
        summary: str | None = None,
        status: str | None = None,
        args: dict[str, JsonValue] | None = None,
    ) -> bool:
        """Update an existing step's fields."""
        with self._lock:
            # First, get the current step
            row = self._conn.execute(
                "SELECT args_json, summary_text, status, session_id FROM steps WHERE id = ?",
                (str(step_id),),
            ).fetchone()

            if row is None:
                return False

            # Merge args
            current_args = json.loads(row["args_json"]) if row["args_json"] else {}
            if args:
                current_args.update(args)

            # Update fields
            new_summary = summary if summary is not None else row["summary_text"]
            new_status = status if status is not None else row["status"]
            new_args_json = json.dumps(current_args, separators=(",", ":"))

            decision: str | None = None
            if args and "decision" in args and isinstance(args["decision"], str):
                decision = args["decision"]

            self._conn.execute(
                """
                UPDATE steps
                SET summary_text = ?, status = ?, args_json = ?, decision = COALESCE(?, decision)
                WHERE id = ?
                """,
                (new_summary, new_status, new_args_json, decision, str(step_id)),
            )

        self._checkpoint()

        # Fetch the updated step and notify via queue
        conn = _connect(self._db_path)
        try:
            with self._lock:
                row = conn.execute(
                    """
                    SELECT
                        id, session_id, created_at, kind, name, status,
                        duration_ms, summary_text, risk_level, warnings_json,
                        target_type, tool_category,
                        sql_text, sql_truncated, sql_classification,
                        policy_rule_ids_json, decision,
                        result_rows_shown, result_rows_total, captured_bytes, error_message,
                        args_json, result_json, preview_text, preview_truncated
                    FROM steps
                    WHERE id = ?
                    """,
                    (str(step_id),),
                ).fetchone()

            if row:
                args_parsed = json.loads(row["args_json"]) if row["args_json"] else None
                result_parsed = json.loads(row["result_json"]) if row["result_json"] else None

                warnings = (
                    json.loads(row["warnings_json"]) if row["warnings_json"] is not None else None
                )
                policy_rule_ids = (
                    json.loads(row["policy_rule_ids_json"])
                    if row["policy_rule_ids_json"] is not None
                    else None
                )

                sql: TruncatedText | None = None
                if row["sql_text"] is not None:
                    sql = TruncatedText(
                        text=row["sql_text"],
                        truncated=bool(row["sql_truncated"]),
                    )

                preview: TruncatedText | None = None
                if row["preview_text"] is not None:
                    preview = TruncatedText(
                        text=row["preview_text"],
                        truncated=bool(row["preview_truncated"]),
                    )

                updated_step = ObservedStep(
                    id=UUID(row["id"]),
                    session_id=UUID(row["session_id"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    kind=cast(ObservedStepKind, row["kind"]),
                    name=row["name"],
                    status=cast(Literal["ok", "error"], row["status"]),
                    duration_ms=row["duration_ms"],
                    summary=row["summary_text"],
                    risk_level=row["risk_level"],
                    warnings=warnings,
                    target_type=row["target_type"],
                    tool_category=row["tool_category"],
                    sql=sql,
                    sql_classification=row["sql_classification"],
                    policy_rule_ids=policy_rule_ids,
                    decision=row["decision"],
                    result_rows_shown=row["result_rows_shown"],
                    result_rows_total=row["result_rows_total"],
                    captured_bytes=row["captured_bytes"],
                    error_message=row["error_message"],
                    args=args_parsed,
                    result=result_parsed,
                    preview=preview,
                )

                session_id = UUID(row["session_id"])
                queue = self._queues.get(session_id)
                if queue is None:
                    queue = asyncio.Queue()
                    self._queues[session_id] = queue
                queue.put_nowait(updated_step)
        finally:
            conn.close()

        return True

    def list_steps(self, session_id: UUID) -> Sequence[ObservedStep]:
        # Create a fresh connection for read operations to ensure WAL visibility
        conn = _connect(self._db_path)
        try:
            with self._lock:
                rows = conn.execute(
                    """
                    SELECT
                        id,
                        session_id,
                        created_at,
                        kind,
                        name,
                        status,
                        duration_ms,
                        summary_text,
                        risk_level,
                        warnings_json,
                        target_type,
                        tool_category,
                        sql_text,
                        sql_truncated,
                        sql_classification,
                        policy_rule_ids_json,
                        decision,
                        result_rows_shown,
                        result_rows_total,
                        captured_bytes,
                        error_message,
                        tables_touched_json,
                        args_json,
                        result_json,
                        preview_text,
                        preview_truncated
                    FROM steps
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    """.strip(),
                    (str(session_id),),
                ).fetchall()

            steps: list[ObservedStep] = []
            for row in rows:
                args = json.loads(row["args_json"]) if row["args_json"] is not None else None
                result = json.loads(row["result_json"]) if row["result_json"] is not None else None

                warnings = (
                    json.loads(row["warnings_json"]) if row["warnings_json"] is not None else None
                )
                tables_touched = (
                    json.loads(row["tables_touched_json"])
                    if row["tables_touched_json"] is not None
                    else None
                )
                policy_rule_ids = (
                    json.loads(row["policy_rule_ids_json"])
                    if row["policy_rule_ids_json"] is not None
                    else None
                )

                sql: TruncatedText | None = None
                if row["sql_text"] is not None:
                    sql = TruncatedText(
                        text=row["sql_text"],
                        truncated=bool(row["sql_truncated"]),
                    )

                preview: TruncatedText | None
                if row["preview_text"] is None:
                    preview = None
                else:
                    preview = TruncatedText(
                        text=row["preview_text"],
                        truncated=bool(row["preview_truncated"]),
                    )

                steps.append(
                    ObservedStep(
                        id=UUID(row["id"]),
                        session_id=UUID(row["session_id"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        kind=cast(ObservedStepKind, row["kind"]),
                        name=row["name"],
                        status=cast(Literal["ok", "error"], row["status"]),
                        duration_ms=row["duration_ms"],
                        summary=row["summary_text"],
                        risk_level=row["risk_level"],
                        warnings=warnings,
                        tables_touched=tables_touched,
                        target_type=row["target_type"],
                        tool_category=row["tool_category"],
                        sql=sql,
                        sql_classification=row["sql_classification"],
                        policy_rule_ids=policy_rule_ids,
                        decision=row["decision"],
                        result_rows_shown=row["result_rows_shown"],
                        result_rows_total=row["result_rows_total"],
                        captured_bytes=row["captured_bytes"],
                        error_message=row["error_message"],
                        args=args,
                        result=result,
                        preview=preview,
                    )
                )
            return steps
        finally:
            conn.close()

    def get_step_queue(self, session_id: UUID) -> asyncio.Queue[ObservedStep] | None:
        if self.get_session(session_id) is None:
            return None

        queue = self._queues.get(session_id)
        if queue is None:
            queue = asyncio.Queue()
            self._queues[session_id] = queue
        return queue

    def add_cast(self, cast_obj: Cast) -> None:
        origin_step_ids_json = (
            json.dumps([str(sid) for sid in cast_obj.origin_step_ids], separators=(",", ":"))
            if cast_obj.origin_step_ids
            else None
        )

        # Extract kind-specific fields
        sql: str | None = None
        rows_json: str | None = None
        total_rows: int | None = None
        vega_lite_spec_json: str | None = None
        data_json: str | None = None
        markdown: str | None = None
        truncated: int = 0

        if isinstance(cast_obj, TableCast):
            sql = cast_obj.sql
            rows_json = json.dumps(cast_obj.rows, separators=(",", ":"))
            total_rows = cast_obj.total_rows
            truncated = 1 if cast_obj.truncated else 0
        else:
            raise ValueError(f"Unsupported cast kind: {cast_obj.kind}")

        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?",
                (str(cast_obj.session_id),),
            ).fetchone()
            if exists is None:
                raise KeyError(cast_obj.session_id)

            self._conn.execute(
                """
                INSERT INTO casts (
                    id, session_id, created_at, kind, title,
                    origin_step_id, origin_step_ids_json,
                    sql, rows_json, total_rows,
                    vega_lite_spec_json, data_json, markdown, truncated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(cast_obj.id),
                    str(cast_obj.session_id),
                    cast_obj.created_at.isoformat(),
                    cast_obj.kind,
                    cast_obj.title,
                    str(cast_obj.origin_step_id),
                    origin_step_ids_json,
                    sql,
                    rows_json,
                    total_rows,
                    vega_lite_spec_json,
                    data_json,
                    markdown,
                    truncated,
                ),
            )
        self._checkpoint()

    def list_casts(self, session_id: UUID) -> Sequence[Cast]:
        # Create a fresh connection for read operations to ensure WAL visibility
        conn = _connect(self._db_path)
        try:
            with self._lock:
                rows = conn.execute(
                    """
                    SELECT
                        id, session_id, created_at, kind, title,
                        origin_step_id, origin_step_ids_json,
                        sql, rows_json, total_rows,
                        vega_lite_spec_json, data_json, markdown, truncated
                    FROM casts
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    """,
                    (str(session_id),),
                ).fetchall()

            return [self._row_to_cast(row) for row in rows]
        finally:
            conn.close()

    def get_cast(self, cast_id: UUID) -> Cast | None:
        # Create a fresh connection for read operations to ensure WAL visibility
        conn = _connect(self._db_path)
        try:
            with self._lock:
                row = conn.execute(
                    """
                    SELECT
                        id, session_id, created_at, kind, title,
                        origin_step_id, origin_step_ids_json,
                        sql, rows_json, total_rows,
                        vega_lite_spec_json, data_json, markdown, truncated
                    FROM casts
                    WHERE id = ?
                    """,
                    (str(cast_id),),
                ).fetchone()

            if row is None:
                return None

            return self._row_to_cast(row)
        finally:
            conn.close()

    def _row_to_cast(self, row: Any) -> Cast:
        """Convert a database row to a Cast object."""
        base_kwargs = {
            "id": UUID(row["id"]),
            "session_id": UUID(row["session_id"]),
            "created_at": datetime.fromisoformat(row["created_at"]),
            "title": row["title"],
            "origin_step_id": UUID(row["origin_step_id"]),
            "origin_step_ids": (
                [UUID(sid) for sid in json.loads(row["origin_step_ids_json"])]
                if row["origin_step_ids_json"]
                else []
            ),
        }

        kind = row["kind"]
        if kind == "table":
            return TableCast(
                **base_kwargs,
                sql=row["sql"],
                rows=json.loads(row["rows_json"]) if row["rows_json"] else [],
                total_rows=row["total_rows"],
                truncated=bool(row["truncated"]),
            )
        else:
            raise ValueError(f"Unknown or unsupported cast kind: {kind}")

    def create_pending_request(
        self,
        *,
        request_id: UUID | None = None,
        session_id: UUID,
        tool_name: str,
        arguments: JsonValue | None,
        classification: str | None,
        risk_level: str | None,
        reason: str | None,
        blocker_step_id: UUID | None,
    ) -> PendingRequest:
        if self.get_session(session_id) is None:
            raise KeyError(session_id)

        req_id = request_id or uuid4()
        created_at = datetime.now(UTC)
        args_json = json.dumps(arguments, separators=(",", ":")) if arguments is not None else None

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO pending_requests (
                    id, session_id, created_at,
                    tool_name, arguments_json,
                    classification, risk_level, reason,
                    blocker_step_id,
                    status, decided_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """.strip(),
                (
                    str(req_id),
                    str(session_id),
                    created_at.isoformat(),
                    tool_name,
                    args_json,
                    classification,
                    risk_level,
                    reason,
                    str(blocker_step_id) if blocker_step_id is not None else None,
                    PendingStatus.pending.value,
                    None,
                ),
            )
        self._checkpoint()

        return PendingRequest(
            id=req_id,
            session_id=session_id,
            created_at=created_at,
            tool_name=tool_name,
            arguments=cast(Any, arguments),
            classification=classification,
            risk_level=risk_level,
            reason=reason,
            blocker_step_id=blocker_step_id,
            status=PendingStatus.pending,
            decided_at=None,
        )

    def get_pending_request(self, request_id: UUID) -> PendingRequest | None:
        conn = _connect(self._db_path)
        try:
            with self._lock:
                row = conn.execute(
                    """
                    SELECT
                        id, session_id, created_at,
                        tool_name, arguments_json,
                        classification, risk_level, reason,
                        blocker_step_id,
                        status, decided_at
                    FROM pending_requests
                    WHERE id = ?
                    """.strip(),
                    (str(request_id),),
                ).fetchone()
            if row is None:
                return None

            args = json.loads(row["arguments_json"]) if row["arguments_json"] is not None else None
            return PendingRequest(
                id=UUID(row["id"]),
                session_id=UUID(row["session_id"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                tool_name=row["tool_name"],
                arguments=args,
                classification=row["classification"],
                risk_level=row["risk_level"],
                reason=row["reason"],
                blocker_step_id=UUID(row["blocker_step_id"]) if row["blocker_step_id"] else None,
                status=PendingStatus(row["status"]),
                decided_at=datetime.fromisoformat(row["decided_at"]) if row["decided_at"] else None,
            )
        finally:
            conn.close()

    def list_pending_requests(
        self, session_id: UUID, *, status: PendingStatus | None = None
    ) -> Sequence[PendingRequest]:
        conn = _connect(self._db_path)
        try:
            sql = """
                SELECT
                    id, session_id, created_at,
                    tool_name, arguments_json,
                    classification, risk_level, reason,
                    blocker_step_id,
                    status, decided_at
                FROM pending_requests
                WHERE session_id = ?
            """.strip()
            params: list[Any] = [str(session_id)]
            if status is not None:
                sql += " AND status = ?"
                params.append(status.value)
            sql += " ORDER BY created_at ASC"

            with self._lock:
                rows = conn.execute(sql, tuple(params)).fetchall()

            items: list[PendingRequest] = []
            for row in rows:
                args = (
                    json.loads(row["arguments_json"]) if row["arguments_json"] is not None else None
                )
                items.append(
                    PendingRequest(
                        id=UUID(row["id"]),
                        session_id=UUID(row["session_id"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        tool_name=row["tool_name"],
                        arguments=args,
                        classification=row["classification"],
                        risk_level=row["risk_level"],
                        reason=row["reason"],
                        blocker_step_id=UUID(row["blocker_step_id"])
                        if row["blocker_step_id"]
                        else None,
                        status=PendingStatus(row["status"]),
                        decided_at=datetime.fromisoformat(row["decided_at"])
                        if row["decided_at"]
                        else None,
                    )
                )
            return items
        finally:
            conn.close()

    def decide_pending_request(
        self, request_id: UUID, *, status: PendingStatus
    ) -> PendingRequest | None:
        from datetime import UTC, datetime

        decided_at = datetime.now(UTC)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id, session_id, created_at,
                    tool_name, arguments_json,
                    classification, risk_level, reason,
                    blocker_step_id,
                    status, decided_at
                FROM pending_requests
                WHERE id = ?
                """.strip(),
                (str(request_id),),
            ).fetchone()
            if row is None:
                return None

            # Idempotent: if already decided, keep existing decided_at/status.
            if row["status"] != PendingStatus.pending.value:
                args = (
                    json.loads(row["arguments_json"]) if row["arguments_json"] is not None else None
                )
                return PendingRequest(
                    id=UUID(row["id"]),
                    session_id=UUID(row["session_id"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    tool_name=row["tool_name"],
                    arguments=args,
                    classification=row["classification"],
                    risk_level=row["risk_level"],
                    reason=row["reason"],
                    blocker_step_id=UUID(row["blocker_step_id"])
                    if row["blocker_step_id"]
                    else None,
                    status=PendingStatus(row["status"]),
                    decided_at=datetime.fromisoformat(row["decided_at"])
                    if row["decided_at"]
                    else None,
                )

            self._conn.execute(
                """
                UPDATE pending_requests
                SET status = ?, decided_at = ?
                WHERE id = ?
                """.strip(),
                (status.value, decided_at.isoformat(), str(request_id)),
            )

        self._checkpoint()
        return self.get_pending_request(request_id)
