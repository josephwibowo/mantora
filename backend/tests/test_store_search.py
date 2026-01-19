from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mantora.models.events import ObservedStep, SessionContext
from mantora.policy.sql_guard import SQLWarning
from mantora.store.sqlite import SQLiteSessionStore


def test_list_sessions_filters(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(db_path)

    # 1. Create session with tag
    s1 = store.create_session(
        title="Session 1",
        context=SessionContext(tag="JIRA-123", branch="main", repo_name="repo-a"),
    )

    # 2. Create session with warnings
    s2 = store.create_session(title="Session 2")
    step_warn = ObservedStep(
        id=uuid4(),
        session_id=s2.id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        warnings=[SQLWarning.SELECT_STAR.value],
    )
    store.add_step(step_warn)

    # 3. Create session with blocks
    s3 = store.create_session(title="Session 3")
    step_block = ObservedStep(
        id=uuid4(),
        session_id=s3.id,
        created_at=datetime.now(UTC),
        kind="blocker",
        name="query",
        status="ok",
        decision="pending",
    )
    store.add_step(step_block)

    # 4. Create plain session
    s4 = store.create_session(title="Plain Session", context=SessionContext(branch="dev"))

    # Test filtering by tag
    res = list(store.list_sessions(tag="JIRA-123"))
    assert len(res) == 1
    assert res[0].id == s1.id

    # Test filtering by branch
    res = list(store.list_sessions(branch="main"))
    assert len(res) == 1
    assert res[0].id == s1.id

    # Test filtering by repo_name
    res = list(store.list_sessions(repo_name="repo-a"))
    assert len(res) == 1
    assert res[0].id == s1.id

    # Test filtering by warnings
    res = list(store.list_sessions(has_warnings=True))
    assert len(res) == 1
    assert res[0].id == s2.id

    # Test filtering by blocks
    res = list(store.list_sessions(has_blocks=True))
    assert len(res) == 1
    assert res[0].id == s3.id

    # Test search query (title)
    res = list(store.list_sessions(q="Plain"))
    assert len(res) == 1
    assert res[0].id == s4.id

    # Test search query (tag)
    res = list(store.list_sessions(q="JIRA"))
    assert len(res) == 1
    assert res[0].id == s1.id

    store.close()
