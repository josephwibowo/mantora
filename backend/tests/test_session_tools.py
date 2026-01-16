"""Tests for session tools."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from mantora.mcp.tools import SessionTools
from mantora.store import MemorySessionStore


@pytest.fixture
def store() -> MemorySessionStore:
    """Create a memory store for testing."""
    return MemorySessionStore()


@pytest.fixture
def session_tools(store: MemorySessionStore) -> SessionTools:
    """Create session tools with memory store."""
    return SessionTools(store)


def test_session_start_creates_session(session_tools: SessionTools) -> None:
    """session_start creates a new session and returns its ID."""
    session_id = session_tools.session_start(title="Test Session")

    # Should be a valid UUID string
    UUID(session_id)

    # Should be the current session
    assert session_tools.session_current() == session_id


def test_session_start_without_title(session_tools: SessionTools) -> None:
    """session_start works without a title."""
    session_id = session_tools.session_start()

    UUID(session_id)
    assert session_tools.session_current() == session_id


def test_session_end_clears_current(session_tools: SessionTools) -> None:
    """session_end clears the current session."""
    session_id = session_tools.session_start(title="Test")

    result = session_tools.session_end(session_id)

    assert result is True
    assert session_tools.session_current() is None


def test_session_end_wrong_id(session_tools: SessionTools) -> None:
    """session_end returns False for wrong session ID."""
    session_tools.session_start(title="Test")

    result = session_tools.session_end("00000000-0000-0000-0000-000000000000")

    assert result is False
    # Current session should still be set
    assert session_tools.session_current() is not None


def test_session_end_invalid_uuid(session_tools: SessionTools) -> None:
    """session_end returns False for invalid UUID."""
    session_tools.session_start(title="Test")

    result = session_tools.session_end("not-a-uuid")

    assert result is False


def test_session_current_no_session(session_tools: SessionTools) -> None:
    """session_current returns None when no session is active."""
    assert session_tools.session_current() is None


def test_ensure_session_creates_if_none(session_tools: SessionTools) -> None:
    """ensure_session creates a session if none exists."""
    assert session_tools.session_current() is None

    session_id = session_tools.ensure_session()

    assert isinstance(session_id, UUID)
    assert session_tools.session_current() == str(session_id)


def test_ensure_session_reuses_existing(session_tools: SessionTools) -> None:
    """ensure_session returns existing session if one exists."""
    original_id = session_tools.session_start(title="Test")

    ensured_id = session_tools.ensure_session()

    assert str(ensured_id) == original_id


def test_multiple_sessions(session_tools: SessionTools) -> None:
    """Starting a new session replaces the current one."""
    first_id = session_tools.session_start(title="First")
    second_id = session_tools.session_start(title="Second")

    assert first_id != second_id
    assert session_tools.session_current() == second_id


def test_session_isolation_per_connection(session_tools: SessionTools) -> None:
    """Sessions are isolated per connection ID."""
    connection_a = uuid4()
    connection_b = uuid4()

    session_a = session_tools.session_start(title="A", connection_id=connection_a)
    session_b = session_tools.session_start(title="B", connection_id=connection_b)

    assert session_a != session_b
    assert session_tools.session_current(connection_id=connection_a) == session_a
    assert session_tools.session_current(connection_id=connection_b) == session_b


def test_get_last_active_at_no_steps(store: MemorySessionStore) -> None:
    """get_last_active_at returns None for session with no steps."""
    session = store.create_session(title="Test")

    last_active = store.get_last_active_at(session.id)

    assert last_active is None


def test_get_last_active_at_with_steps(store: MemorySessionStore) -> None:
    """get_last_active_at returns timestamp of most recent step."""
    from datetime import UTC, datetime, timedelta

    from mantora.models.events import ObservedStep

    session = store.create_session(title="Test")

    # Add two steps with different timestamps
    step1_time = datetime.now(UTC) - timedelta(seconds=60)
    step2_time = datetime.now(UTC)

    step1 = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=step1_time,
        kind="tool_call",
        name="test1",
        status="ok",
    )
    step2 = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=step2_time,
        kind="tool_call",
        name="test2",
        status="ok",
    )

    store.add_step(step1)
    store.add_step(step2)

    last_active = store.get_last_active_at(session.id)

    assert last_active == step2_time


def test_ensure_session_respects_timeout(store: MemorySessionStore) -> None:
    """ensure_session creates new session after timeout."""
    from datetime import UTC, datetime, timedelta

    from mantora.models.events import ObservedStep

    # Use very short timeout (1 second)
    session_tools = SessionTools(store, timeout_seconds=1.0)

    # Create session and add a step
    session_id = session_tools.ensure_session()

    step = ObservedStep(
        id=uuid4(),
        session_id=session_id,  # Already a UUID
        created_at=datetime.now(UTC) - timedelta(seconds=2),  # 2 seconds ago
        kind="tool_call",
        name="test",
        status="ok",
    )
    store.add_step(step)

    # Next ensure_session should create a new session due to timeout
    new_session_id = session_tools.ensure_session()

    assert new_session_id != session_id


def test_ensure_session_reuses_within_timeout(store: MemorySessionStore) -> None:
    """ensure_session reuses session within timeout."""
    from datetime import UTC, datetime

    from mantora.models.events import ObservedStep

    # Use long timeout (1 hour)
    session_tools = SessionTools(store, timeout_seconds=3600.0)

    # Create session and add a step
    session_id = session_tools.ensure_session()

    step = ObservedStep(
        id=uuid4(),
        session_id=session_id,  # Already a UUID
        created_at=datetime.now(UTC),  # Just now
        kind="tool_call",
        name="test",
        status="ok",
    )
    store.add_step(step)

    # Next ensure_session should reuse the same session
    reused_session_id = session_tools.ensure_session()

    assert reused_session_id == session_id


def test_timeout_disabled_with_zero(store: MemorySessionStore) -> None:
    """Timeout is disabled when set to 0."""
    from datetime import UTC, datetime, timedelta

    from mantora.models.events import ObservedStep

    # Disable timeout
    session_tools = SessionTools(store, timeout_seconds=0.0)

    # Create session and add a VERY old step
    session_id = session_tools.ensure_session()

    step = ObservedStep(
        id=uuid4(),
        session_id=session_id,  # Already a UUID
        created_at=datetime.now(UTC) - timedelta(hours=24),  # 24 hours ago
        kind="tool_call",
        name="test",
        status="ok",
    )
    store.add_step(step)

    # Should still reuse the same session
    reused_session_id = session_tools.ensure_session()

    assert reused_session_id == session_id
