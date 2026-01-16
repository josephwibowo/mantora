"""Integration tests for MCP proxy."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

import pytest
from mcp import types

from mantora.config import ProxyConfig, TargetConfig
from mantora.config.settings import PolicyConfig
from mantora.mcp import ForwardContext, MCPProxy, ProxyHooks
from mantora.policy.blocker import PendingStatus
from mantora.store import MemorySessionStore


@pytest.fixture
def store() -> MemorySessionStore:
    """Create a memory store for testing."""
    return MemorySessionStore()


@pytest.fixture
def stub_server_command() -> list[str]:
    """Get the command to run the stub MCP server."""
    stub_path = Path(__file__).parent / "stub_mcp_server.py"
    return [sys.executable, str(stub_path)]


@pytest.fixture
def mock_duckdb_command() -> list[str]:
    """Command to run the mock DuckDB MCP server (supports `query`)."""
    server_path = Path(__file__).parent / "fixtures" / "mock_duckdb_server.py"
    return [sys.executable, str(server_path)]


@pytest.fixture
def proxy_config(stub_server_command: list[str]) -> ProxyConfig:
    """Create proxy config pointing to stub server."""
    return ProxyConfig(
        policy=PolicyConfig(protective_mode=True),
        target=TargetConfig(command=stub_server_command),
    )


def test_proxy_creation(store: MemorySessionStore) -> None:
    """Proxy can be created with config and store."""
    config = ProxyConfig()
    proxy = MCPProxy(config=config, store=store)

    assert proxy.config == config
    assert proxy._session_tools is not None


def test_proxy_session_tool_definitions(store: MemorySessionStore) -> None:
    """Proxy exposes session tool definitions."""
    config = ProxyConfig()
    proxy = MCPProxy(config=config, store=store)

    tools = proxy._get_session_tool_definitions()
    assert len(tools) == 4
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "session_start",
        "session_end",
        "session_current",
        "cast_table",
    }


@pytest.mark.asyncio
async def test_proxy_session_start(store: MemorySessionStore) -> None:
    """Proxy handles session_start tool call."""
    config = ProxyConfig()
    proxy = MCPProxy(config=config, store=store)

    result = await proxy._handle_session_tool("session_start", {"title": "Test"})

    assert len(result) == 1
    assert "Session started:" in result[0].text


@pytest.mark.asyncio
async def test_proxy_session_current_no_session(store: MemorySessionStore) -> None:
    """Proxy handles session_current when no session exists."""
    config = ProxyConfig()
    proxy = MCPProxy(config=config, store=store)

    result = await proxy._handle_session_tool("session_current", {})

    assert len(result) == 1
    assert "No active session" in result[0].text


@pytest.mark.asyncio
async def test_proxy_session_lifecycle(store: MemorySessionStore) -> None:
    """Proxy handles full session lifecycle."""
    config = ProxyConfig()
    proxy = MCPProxy(config=config, store=store)

    # Start session
    start_result = await proxy._handle_session_tool("session_start", {"title": "Test"})
    assert "Session started:" in start_result[0].text
    session_id = start_result[0].text.split(": ")[1]

    # Check current
    current_result = await proxy._handle_session_tool("session_current", {})
    assert session_id in current_result[0].text

    # End session
    end_result = await proxy._handle_session_tool("session_end", {"session_id": session_id})
    assert "Session ended:" in end_result[0].text

    # Check current again
    current_result = await proxy._handle_session_tool("session_current", {})
    assert "No active session" in current_result[0].text


class DenyAllHooks(ProxyHooks):
    """Test hooks that deny all forwarded calls."""

    async def pre_forward(self, ctx: ForwardContext) -> tuple[bool, str | None]:
        return (False, "Test denial")


@pytest.mark.asyncio
async def test_proxy_hooks_deny(store: MemorySessionStore) -> None:
    """Proxy respects pre_forward hook denial."""
    config = ProxyConfig(policy=PolicyConfig(protective_mode=False))
    hooks = DenyAllHooks(config=config)
    proxy = MCPProxy(config=config, store=store, hooks=hooks)

    # Try to call a non-session tool (would be forwarded)
    result = await proxy._handle_tool_call("some_tool", {"arg": "value"})

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    assert "denied" in first_result.text.lower()
    assert "Test denial" in first_result.text


@pytest.mark.asyncio
async def test_proxy_ensures_session_on_forward(store: MemorySessionStore) -> None:
    """Proxy auto-creates session when forwarding if none exists."""
    config = ProxyConfig(policy=PolicyConfig(protective_mode=False))
    proxy = MCPProxy(config=config, store=store)

    # No session initially
    assert proxy._session_tools.session_current() is None

    # Call a non-session tool (triggers ensure_session before forward attempt)
    # This will fail at forward since no target, but session should be created
    await proxy._handle_tool_call("some_tool", {})

    # Session should now exist
    assert proxy._session_tools.session_current() is not None


@pytest.mark.asyncio
async def test_proxy_sql_policy_blocking_denied(store: MemorySessionStore) -> None:
    """Proxy blocks CRITICAL SQL in protective mode and returns denial after user denial."""
    config = ProxyConfig(policy=PolicyConfig(protective_mode=True))
    proxy = MCPProxy(config=config, store=store)
    proxy._blocker_timeout_s = 5.0

    # Start a blocked call in the background (it will wait for a decision)
    task = asyncio.create_task(proxy._handle_tool_call("query", {"sql": "DROP TABLE users"}))

    # Wait until the proxy has created a session and persisted a pending request
    session_id = None
    for _ in range(50):
        sessions = list(store.list_sessions())
        if sessions:
            session_id = sessions[0].id
            pending = list(store.list_pending_requests(session_id, status=PendingStatus.pending))
            if pending:
                store.decide_pending_request(pending[0].id, status=PendingStatus.denied)
                break
        await asyncio.sleep(0.01)

    result = await task

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    assert "denied" in first_result.text.lower()

    # Ensure blocker step is recorded with decision in args
    assert session_id is not None
    steps = list(store.list_steps(session_id))
    blocker_steps = [s for s in steps if s.kind == "blocker"]
    assert len(blocker_steps) == 1
    assert blocker_steps[0].args is not None
    assert isinstance(blocker_steps[0].args, dict)
    assert blocker_steps[0].args.get("decision") == "denied"


@pytest.mark.asyncio
async def test_proxy_sql_policy_blocking_timeout(store: MemorySessionStore) -> None:
    """Proxy auto-denies a blocker if no decision is made within timeout."""
    config = ProxyConfig(policy=PolicyConfig(protective_mode=True))
    proxy = MCPProxy(config=config, store=store)
    proxy._blocker_timeout_s = 0.01

    result = await proxy._handle_tool_call("query", {"sql": "DROP TABLE users"})

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    assert "timeout" in first_result.text.lower()

    session_id_str = proxy._session_tools.session_current()
    assert session_id_str is not None
    session_id = UUID(session_id_str)
    steps = list(store.list_steps(session_id))
    blocker_steps = [s for s in steps if s.kind == "blocker"]
    assert len(blocker_steps) == 1
    assert blocker_steps[0].args is not None
    assert isinstance(blocker_steps[0].args, dict)
    decision = blocker_steps[0].args.get("decision")
    assert isinstance(decision, str)
    assert decision in ("timeout", "denied")


@pytest.mark.asyncio
async def test_proxy_sql_policy_extracts_query_argument_key(store: MemorySessionStore) -> None:
    """Proxy blocks CRITICAL SQL even when the argument key is `query` (not `sql`)."""
    config = ProxyConfig(
        policy=PolicyConfig(protective_mode=True),
        target=TargetConfig(type="duckdb"),
    )
    proxy = MCPProxy(config=config, store=store)
    proxy._blocker_timeout_s = 0.01

    result = await proxy._handle_tool_call("query", {"query": "DROP TABLE users"})

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    assert "timeout" in first_result.text.lower()


@pytest.mark.asyncio
async def test_proxy_sql_policy_blocks_execute_alias(store: MemorySessionStore) -> None:
    """Proxy treats execute-like tools as query category for blocking in protective mode."""
    config = ProxyConfig(
        policy=PolicyConfig(protective_mode=True),
        target=TargetConfig(type="duckdb"),
    )
    proxy = MCPProxy(config=config, store=store)
    proxy._blocker_timeout_s = 0.01

    result = await proxy._handle_tool_call("execute", {"sql": "DELETE FROM users WHERE id = 1"})

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    assert "timeout" in first_result.text.lower()


@pytest.mark.asyncio
async def test_proxy_blocker_allow_forwards_to_target(
    store: MemorySessionStore, mock_duckdb_command: list[str]
) -> None:
    """Approve flow: blocker -> allow -> tool call is forwarded to target."""
    config = ProxyConfig(
        policy=PolicyConfig(protective_mode=True),
        target=TargetConfig(command=mock_duckdb_command),
    )
    proxy = MCPProxy(config=config, store=store)
    proxy._blocker_timeout_s = 5.0

    async with proxy._target_connection():
        task = asyncio.create_task(proxy._handle_tool_call("query", {"sql": "DROP TABLE users"}))

        # Wait until pending is created, then approve.
        session_id = None
        for _ in range(200):
            sessions = list(store.list_sessions())
            if sessions:
                session_id = sessions[0].id
                pending = list(
                    store.list_pending_requests(session_id, status=PendingStatus.pending)
                )
                if pending:
                    store.decide_pending_request(pending[0].id, status=PendingStatus.allowed)
                    break
            await asyncio.sleep(0.01)

        result = await task
        assert len(result) == 1
        first = result[0]
        assert isinstance(first, types.TextContent)
        payload = json.loads(first.text)
        assert payload.get("affected_rows") == 1

        assert session_id is not None
        steps = list(store.list_steps(session_id))
        blocker_steps = [s for s in steps if s.kind == "blocker"]
    assert len(blocker_steps) == 1
    assert blocker_steps[0].args is not None
    assert isinstance(blocker_steps[0].args, dict)
    assert blocker_steps[0].args.get("decision") == "allowed"


@pytest.mark.asyncio
async def test_proxy_unknown_tool_requires_approval(store: MemorySessionStore) -> None:
    """Unknown tools are fail-closed in protective mode."""
    config = ProxyConfig(policy=PolicyConfig(protective_mode=True))
    proxy = MCPProxy(config=config, store=store)
    proxy._blocker_timeout_s = 0.01

    result = await proxy._handle_tool_call("mystery_tool", {"payload": "value"})

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    assert "timeout" in first_result.text.lower() or "blocked" in first_result.text.lower()

    session_id_str = proxy._session_tools.session_current()
    assert session_id_str is not None
    session_id = UUID(session_id_str)
    pending = list(store.list_pending_requests(session_id))
    assert len(pending) == 1
    assert pending[0].reason == "Unknown tool; requires approval in protective mode."


@pytest.mark.asyncio
async def test_proxy_known_safe_tool_allows_forward(store: MemorySessionStore) -> None:
    """Known safe tools in protective mode are not blocked by allowlist checks."""
    config = ProxyConfig(
        policy=PolicyConfig(protective_mode=True),
        target=TargetConfig(type="duckdb"),
    )
    proxy = MCPProxy(config=config, store=store)

    result = await proxy._handle_tool_call("list_tables", {})

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    assert "target server not connected" in first_result.text.lower()

    session_id_str = proxy._session_tools.session_current()
    assert session_id_str is not None
    session_id = UUID(session_id_str)
    pending = list(store.list_pending_requests(session_id))
    assert pending == []


@pytest.mark.asyncio
async def test_proxy_sql_policy_blocks_unrecognized_tool_names(store: MemorySessionStore) -> None:
    """Regression test: unrecognized tool names (e.g., 'query:mantora') are blocked.

    Security fix: Previously, tools not categorized as 'query' bypassed the blocker.
    Agents could exploit this by using namespaced/unrecognized tool names.
    Now any tool call containing dangerous SQL is blocked regardless of name.
    """
    config = ProxyConfig(
        policy=PolicyConfig(protective_mode=True),
        target=TargetConfig(type="duckdb"),
    )
    proxy = MCPProxy(config=config, store=store)
    proxy._blocker_timeout_s = 0.01

    # Unrecognized tool name that should NOT be treated as "query" category
    # But since it contains dangerous SQL, it should still be blocked
    result = await proxy._handle_tool_call(
        "query:mantora",  # Namespaced name - not in adapter's tool list
        {"query": "DELETE FROM orders WHERE created_at > '2025-12-29'"},
    )

    assert len(result) == 1
    first_result = result[0]
    assert isinstance(first_result, types.TextContent)
    # Should be blocked even though tool name is unrecognized
    assert "timeout" in first_result.text.lower()
