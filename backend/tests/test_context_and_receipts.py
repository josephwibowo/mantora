from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from mantora.config.settings import Caps
from mantora.context import ContextResolver
from mantora.export.receipt import generate_pr_receipt
from mantora.models.events import ObservedStep, SessionContext, TruncatedText
from mantora.policy.linter import extract_tables_touched
from mantora.store import MemorySessionStore, SQLiteSessionStore


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
