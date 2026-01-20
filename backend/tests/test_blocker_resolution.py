from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from mantora.api.routes_sessions import get_session_rollup
from mantora.models.events import ObservedStep
from mantora.store.sqlite import SQLiteSessionStore


def test_session_status_clears_after_allowed_decision(tmp_path: Path) -> None:
    """Test that session status is not 'blocked' if the block was allowed."""
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(db_path)
    session = store.create_session(title="Test Session")

    # 1. Add a blocker step
    blocker_step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="blocker",
        name="drop_table",
        status="ok",
        decision="pending",
    )
    store.add_step(blocker_step)

    # Mock request
    mock_request = MagicMock()
    mock_request.app.state.store = store

    # Check status is initially blocked
    rollup_initial = get_session_rollup(session.id, mock_request)
    assert rollup_initial.status == "blocked"
    assert rollup_initial.blocks == 1

    # 2. Add a decision step allowing the block
    decision_step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="blocker_decision",
        name="decision",
        status="ok",
        decision="allowed",
        args={"request_id": str(blocker_step.id)},
    )
    store.add_step(decision_step)

    # 3. Check status is now clean (or at least not blocked)
    rollup_final = get_session_rollup(session.id, mock_request)
    assert rollup_final.status == "clean"
    assert rollup_final.blocks == 0  # Effective blocks should be 0

    store.close()
