from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mantora.app import create_app
from mantora.config.settings import LimitsConfig, Settings, Storage, StorageBackend


def test_smoke_sessions_and_steps(tmp_path: Path) -> None:
    settings = Settings(
        limits=LimitsConfig(retention_days=14),
        storage=Storage(
            backend=StorageBackend.sqlite,
            sqlite_path=tmp_path / "sessions.db",
        ),
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    create = client.post("/api/sessions", json={"title": "demo"})
    assert create.status_code == 200
    session_id = create.json()["session"]["id"]

    sessions = client.get("/api/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1

    add_step = client.post(
        f"/api/sessions/{session_id}/steps",
        json={"kind": "note", "name": "hello", "preview_text": "world"},
    )
    assert add_step.status_code == 200

    steps = client.get(f"/api/sessions/{session_id}/steps")
    assert steps.status_code == 200
    assert len(steps.json()) == 1

    # Delete session
    delete = client.delete(f"/api/sessions/{session_id}")
    assert delete.status_code == 204

    # Verify gone
    get_gone = client.get(f"/api/sessions/{session_id}")
    assert get_gone.status_code == 404

    sessions_after = client.get("/api/sessions")
    assert len(sessions_after.json()) == 0

    # Delete non-existent
    delete_missing = client.delete("/api/sessions/00000000-0000-0000-0000-000000000000")
    assert delete_missing.status_code == 404
