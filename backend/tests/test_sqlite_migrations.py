from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mantora.models.events import ObservedStep, TruncatedText
from mantora.store.sqlite import SQLiteSessionStore


def test_sqlite_schema_migrates_steps_columns_additively(tmp_path: Path) -> None:
    """Ensure older DBs upgrade to include receipt/trace v1 step columns."""
    db_path = tmp_path / "sessions.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE steps (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_ms INTEGER,
                summary_text TEXT,
                risk_level TEXT,
                args_json TEXT,
                result_json TEXT,
                preview_text TEXT,
                preview_truncated INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
            ("00000000-0000-0000-0000-000000000001", "demo", datetime.now(UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    store = SQLiteSessionStore(db_path)
    try:
        conn2 = sqlite3.connect(db_path)
        try:
            cols = {row[1] for row in conn2.execute("PRAGMA table_info(steps)")}
        finally:
            conn2.close()

        assert "warnings_json" in cols
        assert "target_type" in cols
        assert "tool_category" in cols
        assert "sql_text" in cols
        assert "sql_truncated" in cols
        assert "sql_classification" in cols
        assert "policy_rule_ids_json" in cols
        assert "decision" in cols
        assert "result_rows_shown" in cols
        assert "result_rows_total" in cols
        assert "captured_bytes" in cols
        assert "error_message" in cols

        session_id = uuid4()
        store._conn.execute(
            "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
            (str(session_id), "t", datetime.now(UTC).isoformat()),
        )

        step = ObservedStep(
            id=uuid4(),
            session_id=session_id,
            created_at=datetime.now(UTC),
            kind="tool_call",
            name="query",
            status="ok",
            risk_level="LOW",
            warnings=["NO_LIMIT"],
            target_type="duckdb",
            tool_category="query",
            sql=TruncatedText(text="SELECT 1", truncated=False),
            sql_classification="read_only",
            policy_rule_ids=["block_multi_statement"],
            decision=None,
            result_rows_shown=1,
            result_rows_total=1,
            captured_bytes=123,
            error_message=None,
            args={"sql": "SELECT 1"},
            result={"ok": True},
            preview=TruncatedText(text="ok", truncated=False),
        )
        store.add_step(step)

        loaded = list(store.list_steps(session_id))
        assert loaded == [step]
    finally:
        store.close()
