from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

import mantora.store.sqlite as sqlite_store
from mantora.models.events import ObservedStep, TruncatedText
from mantora.store.retention import prune_sqlite_sessions
from mantora.store.sqlite import SQLiteSessionStore


def test_sqlite_store_persists_sessions_and_steps(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"

    store1 = SQLiteSessionStore(db_path)
    session = store1.create_session(title="demo")

    step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="note",
        name="hello",
        status="ok",
        duration_ms=1,
        args={"a": 1},
        result={"b": 2},
        preview=TruncatedText(text="world", truncated=False),
    )
    store1.add_step(step)
    store1.close()

    store2 = SQLiteSessionStore(db_path)

    loaded_session = store2.get_session(session.id)
    assert loaded_session == session

    loaded_steps = list(store2.list_steps(session.id))
    assert loaded_steps == [step]

    assert store2.get_step_queue(session.id) is not None
    assert store2.get_step_queue(uuid4()) is None

    store2.close()


def test_prune_sqlite_sessions_deletes_steps(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"

    store = SQLiteSessionStore(db_path)
    session = store.create_session(title="old")

    step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="note",
        name="old-step",
        status="ok",
    )
    store.add_step(step)
    store.close()

    old_time = datetime.now(UTC) - timedelta(days=30)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "UPDATE sessions SET created_at = ? WHERE id = ?",
            (old_time.isoformat(), str(session.id)),
        )
        conn.commit()
    finally:
        conn.close()

    pruned = prune_sqlite_sessions(db_path=db_path, retention_days=14)
    assert pruned == 1

    store2 = SQLiteSessionStore(db_path)
    assert store2.get_session(session.id) is None
    assert list(store2.list_steps(session.id)) == []
    store2.close()


def test_sqlite_store_delete_session(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(db_path)

    # Create session with steps
    session = store.create_session(title="delete-me")
    step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="note",
        name="hello",
        status="ok",
    )
    store.add_step(step)

    # Verify it exists
    assert store.get_session(session.id) is not None
    assert len(list(store.list_steps(session.id))) == 1

    # Delete it
    deleted = store.delete_session(session.id)
    assert deleted is True

    # Verify it's gone
    assert store.get_session(session.id) is None
    assert len(list(store.list_steps(session.id))) == 0

    # Delete non-existent
    deleted_again = store.delete_session(uuid4())
    assert deleted_again is False

    store.close()


def test_sqlite_store_prunes_every_100_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "sessions.db"
    calls: list[tuple[Path, int, int | None]] = []

    caplog.set_level(logging.WARNING)

    def fake_prune(*, db_path: Path, retention_days: int, max_db_bytes: int | None = None) -> int:
        calls.append((db_path, retention_days, max_db_bytes))
        return 0

    monkeypatch.setattr(sqlite_store, "prune_sqlite_sessions", fake_prune)
    store = SQLiteSessionStore(db_path, retention_days=1, max_db_bytes=0)
    session = store.create_session(title="demo")

    for _ in range(100):
        step = ObservedStep(
            id=uuid4(),
            session_id=session.id,
            created_at=datetime.now(UTC),
            kind="note",
            name="tick",
            status="ok",
        )
        store.add_step(step)

    assert len(calls) == 1
    assert calls[0][1] == 1
    store.close()


def test_prune_sqlite_sessions_respects_max_db_bytes(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"

    store = SQLiteSessionStore(db_path, retention_days=0, max_db_bytes=0)
    session = store.create_session(title="demo")
    store.add_step(
        ObservedStep(
            id=uuid4(),
            session_id=session.id,
            created_at=datetime.now(UTC),
            kind="note",
            name="hello",
            status="ok",
        )
    )
    store.close()

    pruned = prune_sqlite_sessions(db_path=db_path, retention_days=0, max_db_bytes=1)
    assert pruned >= 1

    store2 = SQLiteSessionStore(db_path, retention_days=0, max_db_bytes=0)
    assert list(store2.list_sessions()) == []
    store2.close()
