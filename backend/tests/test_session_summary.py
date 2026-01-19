from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from mantora.api.routes_sessions import _compute_summary, get_session_rollup
from mantora.models.events import ObservedStep
from mantora.store.sqlite import SQLiteSessionStore


def test_compute_summary_aggregates_counts() -> None:
    """Test that _compute_summary correctly counts step types."""
    steps = [
        # Tool call: query (counts as tool_call + query)
        ObservedStep(
            id=uuid4(),
            session_id=uuid4(),
            created_at=datetime.now(UTC),
            kind="tool_call",
            name="query",
            status="ok",
        ),
        # Tool call: cast_table (counts as tool_call + query + cast)
        ObservedStep(
            id=uuid4(),
            session_id=uuid4(),
            created_at=datetime.now(UTC),
            kind="tool_call",
            name="cast_table",
            status="ok",
        ),
        # Tool call: generic (counts as tool_call only)
        ObservedStep(
            id=uuid4(),
            session_id=uuid4(),
            created_at=datetime.now(UTC),
            kind="tool_call",
            name="list_tables",
            status="ok",
        ),
        # Blocker (counts as block)
        ObservedStep(
            id=uuid4(),
            session_id=uuid4(),
            created_at=datetime.now(UTC),
            kind="blocker",
            name="delete_production",
            status="ok",
        ),
        # Error status (counts as error)
        ObservedStep(
            id=uuid4(),
            session_id=uuid4(),
            created_at=datetime.now(UTC),
            kind="tool_call",
            name="broken_tool",
            status="error",
        ),
        # Warnings (counts as warnings)
        ObservedStep(
            id=uuid4(),
            session_id=uuid4(),
            created_at=datetime.now(UTC),
            kind="tool_call",
            name="query",
            status="ok",
            warnings=["SELECT_STAR", "NO_LIMIT"],  # 2 warnings
        ),
    ]

    summary = _compute_summary(steps)

    assert summary.tool_calls == 5  # query, cast_table, list_tables, broken_tool, query(warnings)
    assert summary.queries == 3  # query, cast_table, query(warnings)
    assert summary.casts == 1  # cast_table
    assert summary.blocks == 1  # blocker
    assert summary.errors == 1  # broken_tool
    assert summary.warnings == 2  # From the last step


def test_session_rollup_aggregates_tables(tmp_path: Path) -> None:
    """Test that session rollup correctly aggregates touched tables."""
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(db_path)
    session = store.create_session(title="Test Session")

    # Step touching users table
    step1 = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        tables_touched=["users"],
        duration_ms=100,
    )
    store.add_step(step1)

    # Step touching orders table
    step2 = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        tables_touched=["orders"],
        duration_ms=200,
    )
    store.add_step(step2)

    # Step touching users and products
    step3 = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        tables_touched=["users", "products"],
        duration_ms=150,
    )
    store.add_step(step3)

    # Mock request to return our store
    mock_request = MagicMock()
    mock_request.app.state.store = store

    # Call rollup endpoint function directly
    rollup = get_session_rollup(session.id, mock_request)

    assert rollup.tool_calls == 3
    assert rollup.queries == 3
    assert rollup.tables_touched is not None
    assert set(rollup.tables_touched) == {"users", "orders", "products"}
    assert rollup.duration_ms_total == 450
    assert rollup.status == "clean"

    # Add a warning step and checks status
    step_warn = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        warnings=["WARNING"],
    )
    store.add_step(step_warn)

    rollup_warn = get_session_rollup(session.id, mock_request)
    assert rollup_warn.status == "warnings"
    assert rollup_warn.warnings == 1

    # Add a blocker step
    step_block = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=datetime.now(UTC),
        kind="blocker",
        name="drop_table",
        status="ok",
        decision="pending",
    )
    store.add_step(step_block)

    rollup_block = get_session_rollup(session.id, mock_request)
    assert rollup_block.status == "blocked"
    assert rollup_block.blocks == 1

    store.close()
