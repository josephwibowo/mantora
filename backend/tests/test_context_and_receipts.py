from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from mantora.config.settings import Caps
from mantora.context import ContextResolver
from mantora.export.receipt import generate_pr_receipt
from mantora.models.events import ObservedStep, SessionContext, TruncatedText
from mantora.policy.linter import extract_tables_touched
from mantora.store import MemorySessionStore, SessionStore, SQLiteSessionStore


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@pytest.mark.skipif(
    shutil.which("git") is None, reason="git is required for context resolver tests"
)
def test_context_resolver_detects_git_branch_commit_and_dirty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")

    resolver = ContextResolver()
    ctx = resolver.resolve(project_root=repo)
    assert ctx is not None
    assert ctx.config_source == "cli"
    assert ctx.repo_name == "repo"
    assert ctx.branch == "main"
    assert ctx.commit is not None and len(ctx.commit) == 40
    assert ctx.dirty is False

    (repo / "README.md").write_text("hello world\n", encoding="utf-8")
    ctx2 = resolver.resolve(project_root=repo)
    assert ctx2 is not None
    assert ctx2.dirty is True


@pytest.mark.skipif(
    shutil.which("git") is None, reason="git is required for context resolver tests"
)
def test_context_resolver_env_and_pinned_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "a.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "init")

    resolver = ContextResolver()

    monkeypatch.chdir(repo)
    monkeypatch.delenv("MANTORA_PROJECT_ROOT", raising=False)
    ctx = resolver.resolve()
    assert ctx is not None
    assert ctx.config_source == "git"

    (repo / ".mantora.toml").write_text('project_root = "."\ntag = "JIRA-123"\n', encoding="utf-8")
    ctx2 = resolver.resolve()
    assert ctx2 is not None
    assert ctx2.config_source == "pinned"
    assert ctx2.tag == "JIRA-123"

    monkeypatch.setenv("MANTORA_PROJECT_ROOT", str(repo))
    ctx3 = resolver.resolve()
    assert ctx3 is not None
    assert ctx3.config_source == "env"


@pytest.mark.skipif(
    shutil.which("git") is None, reason="git is required for context resolver tests"
)
def test_context_resolver_can_infer_repo_from_hint_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")

    db_path = repo / "demo.duckdb"
    db_path.write_text("", encoding="utf-8")

    resolver = ContextResolver()

    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    ctx = resolver.resolve(hint_paths=[db_path])
    assert ctx is not None
    assert ctx.repo_name == "repo"
    assert ctx.branch == "main"
    assert ctx.commit is not None and len(ctx.commit) == 40


def test_extract_tables_touched_joins_and_schema_qualified() -> None:
    tables = extract_tables_touched(
        "WITH t AS (SELECT 1) SELECT * FROM foo.bar JOIN baz b ON b.id = 1"
    )
    assert tables is not None
    assert "foo.bar" in tables
    assert "baz" in tables


def test_generate_pr_receipt_includes_context_and_truncates_sql(tmp_path: Path) -> None:
    store = MemorySessionStore()
    context = SessionContext(
        repo_name="repo", branch="main", commit="a" * 40, dirty=False, tag="T-1"
    )
    session = store.create_session(title="demo", context=context)

    long_sql = "SELECT 1\n" + ("-- filler\n" * 5000)
    step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=session.created_at,
        kind="tool_call",
        name="query",
        status="ok",
        duration_ms=12,
        warnings=["NO_LIMIT"],
        tables_touched=["foo.bar"],
        sql=TruncatedText(text=long_sql, truncated=False),
        args={"sql": long_sql},
        result={"ok": True},
        preview=None,
    )
    store.add_step(step)

    res = generate_pr_receipt(store=store, session_id=session.id, caps=Caps(), include_data=False)
    assert "<details>" in res.markdown
    assert "Repo:" in res.markdown
    assert "foo.bar" in res.markdown
    assert res.included_data is False
    assert res.format == "gfm"
    # Verify emoji is present (warnings status)
    assert "⚠️" in res.markdown


def test_pr_receipt_blocked_status_shows_emoji_and_annotation(tmp_path: Path) -> None:
    """Test that blocked sessions show emoji in header and annotate the blocker SQL."""
    store = MemorySessionStore()
    context = SessionContext(
        repo_name="mantora-mcp", branch="feat/test-infra", commit="a" * 40, dirty=False
    )
    session = store.create_session(title="Dangerous Query", context=context)

    # Add a regular query
    select_step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=session.created_at,
        kind="tool_call",
        name="query",
        status="ok",
        duration_ms=10,
        warnings=["SELECT_STAR"],
        tables_touched=["orders"],
        sql=TruncatedText(
            text="SELECT * FROM orders WHERE created_at > '2025-12-29'", truncated=False
        ),
        args={"sql": "SELECT * FROM orders WHERE created_at > '2025-12-29'"},
        result={"ok": True},
        preview=None,
    )
    store.add_step(select_step)

    # Add a blocker step
    blocker_step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=session.created_at,
        kind="blocker",
        name="query",
        status="ok",  # status field only accepts 'ok' or 'error'
        duration_ms=5,
        warnings=["DML"],
        tables_touched=["orders"],
        sql=TruncatedText(
            text="DELETE FROM orders WHERE created_at > '2025-12-29'", truncated=False
        ),
        args={"sql": "DELETE FROM orders WHERE created_at > '2025-12-29'"},
        result=None,
        preview=None,
    )
    store.add_step(blocker_step)

    res = generate_pr_receipt(store=store, session_id=session.id, caps=Caps(), include_data=False)

    # Verify blocked emoji and Protective Mode in header (P2)
    assert "🛑" in res.markdown
    assert "Mantora — Blocked • Protective Mode" in res.markdown

    # Verify the timeline table exists (P0)
    assert "### Timeline" in res.markdown
    assert "| Time | t+ | # | Type | Status | Table | Note |" in res.markdown

    # Verify step-linked SQL with step numbers (P0)
    assert "**Step 1 — QUERY**" in res.markdown
    assert "**Step 2 — MUTATION**" in res.markdown
    assert "🛑 Blocked" in res.markdown
    assert "t+0ms" in res.markdown

    # Verify "At a glance" summary exists (P0)
    assert "**Tables:** `orders` · **Warnings:** DML, SELECT_STAR · **Blocks:** 1" in res.markdown

    # Verify session ID is present as a footer (P2)
    assert f"**Session ID:** `{session.id}`" in res.markdown


def test_pr_receipt_plain_format_has_no_html_tags(tmp_path: Path) -> None:
    store = MemorySessionStore()
    session = store.create_session(title="Plain Test", context=None)
    step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=session.created_at,
        kind="tool_call",
        name="query",
        status="ok",
        duration_ms=12,
        warnings=["SELECT_STAR"],
        tables_touched=["orders"],
        sql=TruncatedText(text="SELECT * FROM orders", truncated=False),
        args={"sql": "SELECT * FROM orders"},
        result={"ok": True},
        preview=None,
    )
    store.add_step(step)

    res = generate_pr_receipt(
        store=store,
        session_id=session.id,
        caps=Caps(),
        include_data=False,
        format="plain",
    )
    assert res.format == "plain"
    assert "<details>" not in res.markdown
    assert "<summary>" not in res.markdown


def test_pr_receipt_gfm_has_br_after_summary(tmp_path: Path) -> None:
    store = MemorySessionStore()
    session = store.create_session(title="BR Test", context=None)
    res = generate_pr_receipt(
        store=store,
        session_id=session.id,
        caps=Caps(),
        include_data=False,
        format="gfm",
    )
    assert res.format == "gfm"
    assert "</summary>\n\n<br/>" in res.markdown


def test_pr_receipt_deduplicates_identical_sql(tmp_path: Path) -> None:
    """Test that identical SQL queries are deduplicated in the receipt."""
    store = MemorySessionStore()
    context = SessionContext(repo_name="repo", branch="main", commit="a" * 40, dirty=False)
    session = store.create_session(title="Dedup Test", context=context)

    # Add 3 identical queries
    for _ in range(3):
        step = ObservedStep(
            id=uuid4(),
            session_id=session.id,
            created_at=session.created_at,
            kind="tool_call",
            name="query",
            status="ok",
            duration_ms=10,
            tables_touched=["t1"],
            sql=TruncatedText(text="SELECT 1", truncated=False),
            args={"sql": "SELECT 1"},
        )
        store.add_step(step)

    res = generate_pr_receipt(store=store, session_id=session.id, caps=Caps(), include_data=False)

    # Timeline should show all 3
    assert "| 1 | QUERY |" in res.markdown
    assert "| 2 | QUERY |" in res.markdown
    assert "| 3 | QUERY |" in res.markdown

    # Detail section should show it once with count
    assert "**Step 1, 2, 3 — QUERY (×3)" in res.markdown  # noqa: RUF001
    assert "SELECT 1" in res.markdown
    # Should not appear multiple times in details (rough check)
    assert res.markdown.count("```sql\nSELECT 1\n```") == 1


def test_sqlite_list_sessions_filters_by_context(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(db_path)
    try:
        s1 = store.create_session(
            title="one",
            context=SessionContext(repo_name="r1", branch="b1", commit="a" * 40, dirty=False),
        )
        s2 = store.create_session(
            title="two",
            context=SessionContext(repo_name="r2", branch="b2", commit="b" * 40, dirty=False),
        )

        assert {s.id for s in store.list_sessions(repo_name="r1")} == {s1.id}
        assert {s.id for s in store.list_sessions(branch="b2")} == {s2.id}
    finally:
        store.close()


def test_sqlite_client_defaults_and_session_client_id(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(db_path)
    try:
        session = store.create_session(title="one", context=None, client_id="client-1")
        assert store.get_session_client_id(session.id) == "client-1"

        assert store.get_client_default_repo_root("client-1") is None
        store.set_client_default_repo_root("client-1", repo_root="/tmp/repo")
        assert store.get_client_default_repo_root("client-1") == "/tmp/repo"

        context = SessionContext(
            repo_root="/tmp/repo",
            repo_name="repo",
            branch="main",
            commit="a" * 40,
            dirty=False,
            config_source="ui",
            tag="T-1",
        )
        updated = store.update_session_context(session.id, context=context)
        assert updated is not None
        assert updated.context is not None
        assert updated.context.repo_root == "/tmp/repo"
        assert updated.context.config_source == "ui"
    finally:
        store.close()


def _create_blocked_session(store: SessionStore) -> UUID:
    context = SessionContext(
        repo_name="mantora-mcp", branch="feat/test-infra", commit="a" * 40, dirty=False
    )
    session = store.create_session(title="Dangerous Query", context=context)

    # Add a regular query
    select_step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=session.created_at,
        kind="tool_call",
        name="query",
        status="ok",
        duration_ms=10,
        warnings=["SELECT_STAR"],
        tables_touched=["orders"],
        sql=TruncatedText(
            text="SELECT * FROM orders WHERE created_at > '2025-12-29'", truncated=False
        ),
        args={"sql": "SELECT * FROM orders"},
        result={"ok": True},
        preview=None,
    )
    store.add_step(select_step)

    # Add a blocker step
    blocker_step = ObservedStep(
        id=uuid4(),
        session_id=session.id,
        created_at=session.created_at,
        kind="blocker",
        name="query",
        status="ok",
        duration_ms=5,
        warnings=["DML"],
        tables_touched=["orders"],
        sql=TruncatedText(
            text="DELETE FROM orders WHERE created_at > '2025-12-29'", truncated=False
        ),
        args={"sql": "DELETE FROM orders"},
        result=None,
        preview=None,
    )
    store.add_step(blocker_step)
    return session.id


def test_pr_receipt_plain_format_no_html_tags() -> None:
    store = MemorySessionStore()
    session_id = _create_blocked_session(store)

    result = generate_pr_receipt(
        store=store,
        session_id=session_id,
        caps=Caps(),
        format="plain",
    )

    assert result.format == "plain"
    assert "<details>" not in result.markdown
    assert "<summary>" not in result.markdown
    assert "════" in result.markdown
    assert "MANTORA SESSION" in result.markdown
    assert "Step 1" in result.markdown


def test_pr_receipt_gfm_has_br_after_summary_new() -> None:
    store = MemorySessionStore()
    session_id = _create_blocked_session(store)

    result = generate_pr_receipt(
        store=store,
        session_id=session_id,
        caps=Caps(),
        format="gfm",
    )

    assert result.format == "gfm"
    assert "summary><strong>" in result.markdown
    assert "<br/>" in result.markdown


def test_pr_receipt_gfm_timeline_includes_t_plus() -> None:
    store = MemorySessionStore()
    session_id = _create_blocked_session(store)

    result = generate_pr_receipt(
        store=store,
        session_id=session_id,
        caps=Caps(),
        format="gfm",
    )

    assert "| t+ |" in result.markdown
    # Check for t+ in step details meta
    assert "t+" in result.markdown
