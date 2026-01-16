from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from mantora.app import create_app
from mantora.casts.models import TableCast
from mantora.config.settings import Caps, Settings, Storage, StorageBackend
from mantora.models.events import ObservedStep, TruncatedText


def test_export_json_includes_steps_in_order() -> None:
    settings = Settings(storage=Storage(backend=StorageBackend.memory))
    app = create_app(settings=settings)
    client = TestClient(app)

    store = app.state.store
    session = store.create_session(title="demo")

    step1 = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        kind="note",
        name="first",
        status="ok",
        duration_ms=None,
        args={"a": 1},
        result={"b": 2},
        preview=TruncatedText(text="hello", truncated=False),
    )
    step2 = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        kind="note",
        name="second",
        status="ok",
        duration_ms=None,
        args={"a": 2},
        result={"b": 3},
        preview=TruncatedText(text="world", truncated=False),
    )
    store.add_step(step1)
    store.add_step(step2)

    resp = client.get(f"/api/sessions/{session.id}/export.json")
    assert resp.status_code == 200
    data = json.loads(resp.text)

    assert data["schema_version"] == "mantora.session.v0"
    assert data["session"]["id"] == str(session.id)
    assert [s["name"] for s in data["steps"]] == ["first", "second"]


def test_export_md_contains_timeline_headings_and_cast_evidence() -> None:
    settings = Settings(storage=Storage(backend=StorageBackend.memory))
    app = create_app(settings=settings)
    client = TestClient(app)

    store = app.state.store
    session = store.create_session(title="demo")

    origin_step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        kind="tool_call",
        name="run query",
        status="ok",
        duration_ms=12,
        args=None,
        result=None,
        preview=TruncatedText(text="SELECT 1", truncated=False),
    )
    store.add_step(origin_step)

    cast = TableCast(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
        title="Result table",
        origin_step_id=origin_step.id,
        origin_step_ids=[],
        sql="SELECT 1",
        rows=[{"x": 1}],
        total_rows=1,
        truncated=False,
    )
    store.add_cast(cast)

    resp = client.get(f"/api/sessions/{session.id}/export.md")
    assert resp.status_code == 200
    text = resp.text

    assert "## Timeline" in text
    assert "### 1. run query" in text
    assert "## Casts" in text
    assert "### Result table" in text
    assert f"`{origin_step.id}`" in text


def test_export_respects_max_preview_rows_cap() -> None:
    settings = Settings(
        storage=Storage(backend=StorageBackend.memory),
        caps=Caps(max_preview_rows=2, max_preview_payload_bytes=512 * 1024, max_columns=80),
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    store = app.state.store
    session = store.create_session(title="demo")

    for i in range(3):
        store.add_step(
            ObservedStep(
                id=uuid4(),
                session_id=session.id,
                created_at=datetime(2026, 1, 1, 0, i, tzinfo=UTC),
                kind="note",
                name=f"step-{i}",
                status="ok",
                duration_ms=None,
                args=None,
                result=None,
                preview=TruncatedText(text="x", truncated=False),
            )
        )

    resp = client.get(f"/api/sessions/{session.id}/export.json")
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert len(data["steps"]) == 2
    assert data["truncation"]["steps_truncated"] is True


def test_export_md_blockers_golden_snapshot() -> None:
    settings = Settings(storage=Storage(backend=StorageBackend.memory))
    app = create_app(settings=settings)
    client = TestClient(app)

    store = app.state.store
    session = store.create_session(title="demo")

    # Make session id deterministic for snapshot by overwriting the stored session.
    fixed_session_id = UUID("00000000-0000-0000-0000-000000000001")
    store._sessions[fixed_session_id] = store._sessions.pop(session.id)
    store._sessions[fixed_session_id] = store._sessions[fixed_session_id].model_copy(
        update={"id": fixed_session_id, "created_at": datetime(2026, 1, 1, 0, 0, tzinfo=UTC)}
    )
    store._steps[fixed_session_id] = store._steps.pop(session.id)
    store._queues[fixed_session_id] = store._queues.pop(session.id)
    store._session_casts[fixed_session_id] = store._session_casts.pop(session.id)
    session_id = fixed_session_id

    # Blocker + decision steps with fixed ids and timestamps
    pending_id = "00000000-0000-0000-0000-000000000099"
    blocker = ObservedStep(
        id=UUID("00000000-0000-0000-0000-000000000101"),
        session_id=session_id,
        created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        kind="blocker",
        name="query",
        status="ok",
        duration_ms=None,
        summary="Blocked: Destructive SQL is not allowed in protective mode",
        risk_level="CRITICAL",
        args={
            "request_id": pending_id,
            "sql": "DROP TABLE users",
            "reason": "Destructive SQL is not allowed in protective mode",
            "classification": "destructive",
            "risk_level": "CRITICAL",
        },
        result=None,
        preview=None,
    )
    decision = ObservedStep(
        id=UUID("00000000-0000-0000-0000-000000000102"),
        session_id=session_id,
        created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
        kind="blocker_decision",
        name="query",
        status="ok",
        duration_ms=None,
        summary="Denied blocked query request",
        risk_level="CRITICAL",
        args={
            "request_id": pending_id,
            "decision": "denied",
            "sql": "DROP TABLE users",
            "reason": "Destructive SQL is not allowed in protective mode",
            "classification": "destructive",
            "risk_level": "CRITICAL",
        },
        result=None,
        preview=None,
    )
    note = ObservedStep(
        id=UUID("00000000-0000-0000-0000-000000000103"),
        session_id=session_id,
        created_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
        kind="note",
        name="note",
        status="ok",
        duration_ms=None,
        args={"hello": "world"},
        result={"ok": True},
        preview=None,
    )
    store.add_step(blocker)
    store.add_step(decision)
    store.add_step(note)

    resp = client.get(f"/api/sessions/{session_id}/export.md")
    assert resp.status_code == 200

    golden_path = Path(__file__).parent / "golden" / "export_with_blockers.md"
    golden = golden_path.read_text(encoding="utf-8")
    assert resp.text == golden
