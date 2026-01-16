"""Tests for policy hooks integration."""

from __future__ import annotations

from typing import Any

import pytest
from mcp import types

from mantora.config import ProxyConfig
from mantora.config.settings import LimitsConfig, PolicyConfig
from mantora.mcp import ForwardContext
from mantora.mcp.policy_hooks import PolicyHooks


@pytest.fixture
def protective_hooks() -> PolicyHooks:
    """Create hooks in protective mode."""
    return PolicyHooks(
        config=ProxyConfig(),
        policy=PolicyConfig(protective_mode=True),
        target_type="duckdb",
    )


@pytest.fixture
def transparent_hooks() -> PolicyHooks:
    """Create hooks in transparent mode."""
    return PolicyHooks(
        config=ProxyConfig(),
        policy=PolicyConfig(protective_mode=False),
        target_type="duckdb",
    )


def make_context(tool_name: str, arguments: dict[str, Any]) -> ForwardContext:
    """Create a forward context for testing."""
    return ForwardContext(
        session_id="test-session",
        tool_name=tool_name,
        arguments=arguments,
    )


class TestPreForwardProtectiveMode:
    """Tests for pre_forward hook in protective mode."""

    @pytest.mark.asyncio
    async def test_allows_read_only_sql(self, protective_hooks: PolicyHooks) -> None:
        """Read-only SQL is allowed in protective mode."""
        ctx = make_context("query", {"sql": "SELECT * FROM users"})
        should_forward, reason = await protective_hooks.pre_forward(ctx)
        assert should_forward
        assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_destructive_sql(self, protective_hooks: PolicyHooks) -> None:
        """Destructive SQL is allowed at the hook layer (blocker flow is handled by MCPProxy)."""
        ctx = make_context("query", {"sql": "DELETE FROM users WHERE id = 1"})
        should_forward, reason = await protective_hooks.pre_forward(ctx)
        assert should_forward
        assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_insert(self, protective_hooks: PolicyHooks) -> None:
        """INSERT is allowed at the hook layer (blocker flow is handled by MCPProxy)."""
        ctx = make_context("query", {"sql": "INSERT INTO users (name) VALUES ('test')"})
        should_forward, _reason = await protective_hooks.pre_forward(ctx)
        assert should_forward

    @pytest.mark.asyncio
    async def test_blocks_update(self, protective_hooks: PolicyHooks) -> None:
        """UPDATE is allowed at the hook layer (blocker flow is handled by MCPProxy)."""
        ctx = make_context("query", {"sql": "UPDATE users SET name = 'new'"})
        should_forward, _reason = await protective_hooks.pre_forward(ctx)
        assert should_forward

    @pytest.mark.asyncio
    async def test_blocks_ddl(self, protective_hooks: PolicyHooks) -> None:
        """DDL statements are allowed at the hook layer (blocker flow is handled by MCPProxy)."""
        for sql in [
            "DROP TABLE users",
            "CREATE TABLE new_table (id INT)",
            "ALTER TABLE users ADD COLUMN email TEXT",
        ]:
            ctx = make_context("query", {"sql": sql})
            should_forward, _reason = await protective_hooks.pre_forward(ctx)
            assert should_forward, f"Expected {sql} to be allowed at hook layer"

    @pytest.mark.asyncio
    async def test_blocks_multi_statement(self, protective_hooks: PolicyHooks) -> None:
        """Multi-statement SQL is allowed at the hook layer (blocker flow is in MCPProxy)."""
        ctx = make_context("query", {"sql": "SELECT 1; SELECT 2"})
        should_forward, reason = await protective_hooks.pre_forward(ctx)
        assert should_forward
        assert reason is None

    @pytest.mark.asyncio
    async def test_allows_no_sql_tools(self, protective_hooks: PolicyHooks) -> None:
        """Tools without SQL are allowed."""
        ctx = make_context("list_tables", {})
        should_forward, reason = await protective_hooks.pre_forward(ctx)
        assert should_forward
        assert reason is None


class TestPreForwardTransparentMode:
    """Tests for pre_forward hook in transparent mode."""

    @pytest.mark.asyncio
    async def test_allows_destructive_sql(self, transparent_hooks: PolicyHooks) -> None:
        """Destructive SQL is allowed in transparent mode."""
        ctx = make_context("query", {"sql": "DELETE FROM users"})
        should_forward, reason = await transparent_hooks.pre_forward(ctx)
        assert should_forward
        assert reason is None

    @pytest.mark.asyncio
    async def test_allows_multi_statement(self, transparent_hooks: PolicyHooks) -> None:
        """Multi-statement SQL is allowed in transparent mode."""
        ctx = make_context("query", {"sql": "SELECT 1; SELECT 2"})
        should_forward, reason = await transparent_hooks.pre_forward(ctx)
        assert should_forward
        assert reason is None


class TestPostResponse:
    """Tests for post_response hook (caps enforcement)."""

    @pytest.fixture
    def hooks_with_caps(self) -> PolicyHooks:
        """Create hooks with small caps for testing."""
        return PolicyHooks(
            config=ProxyConfig(),
            policy=PolicyConfig(protective_mode=True),
            limits=LimitsConfig(preview_rows=5, preview_bytes=100, preview_columns=3),
            target_type="duckdb",
        )

    def make_call_result(self, text: str) -> types.CallToolResult:
        """Create a CallToolResult with text content."""
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
            isError=False,
        )

    @pytest.mark.asyncio
    async def test_caps_text_content(self, hooks_with_caps: PolicyHooks) -> None:
        """Text content is capped."""
        ctx = make_context("query", {"sql": "SELECT * FROM users"})
        result = self.make_call_result("a" * 200)

        capped = await hooks_with_caps.post_response(ctx, result)

        assert len(capped.content) == 1
        text = capped.content[0].text
        # Should be truncated and have marker
        assert "[Preview truncated:" in text

    @pytest.mark.asyncio
    async def test_no_truncation_under_limit(self, hooks_with_caps: PolicyHooks) -> None:
        """Content under limit is not truncated."""
        ctx = make_context("query", {"sql": "SELECT 1"})
        result = self.make_call_result("short text")

        capped = await hooks_with_caps.post_response(ctx, result)

        assert len(capped.content) == 1
        text = capped.content[0].text
        assert text == "short text"
        assert "[Preview truncated:" not in text

    @pytest.mark.asyncio
    async def test_preserves_non_text_content(self, hooks_with_caps: PolicyHooks) -> None:
        """Non-text content is passed through unchanged."""
        ctx = make_context("query", {})
        image_content = types.ImageContent(type="image", data="base64data", mimeType="image/png")
        result = types.CallToolResult(content=[image_content], isError=False)

        capped = await hooks_with_caps.post_response(ctx, result)

        assert len(capped.content) == 1
        assert capped.content[0] == image_content

    @pytest.mark.asyncio
    async def test_caps_always_enforced(self, transparent_hooks: PolicyHooks) -> None:
        """Caps are enforced even in transparent mode."""
        # Use hooks with small caps
        hooks = PolicyHooks(
            config=ProxyConfig(),
            policy=PolicyConfig(protective_mode=False),
            limits=LimitsConfig(preview_bytes=50),
            target_type="duckdb",
        )
        ctx = make_context("query", {"sql": "SELECT * FROM users"})
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text="a" * 200)],
            isError=False,
        )

        capped = await hooks.post_response(ctx, result)

        text = capped.content[0].text
        assert "[Preview truncated:" in text

    @pytest.mark.asyncio
    async def test_handles_non_mcp_result(self, hooks_with_caps: PolicyHooks) -> None:
        """Non-MCP results are passed through unchanged."""
        ctx = make_context("query", {})
        result = {"raw": "data"}

        capped = await hooks_with_caps.post_response(ctx, result)

        assert capped == result


class TestAdapterIntegration:
    """Tests for adapter integration in policy hooks."""

    @pytest.mark.asyncio
    async def test_uses_correct_adapter(self) -> None:
        """Hooks use the configured adapter for SQL extraction."""
        hooks = PolicyHooks(
            config=ProxyConfig(),
            policy=PolicyConfig(protective_mode=True),
            target_type="postgres",
        )
        assert hooks._extract_sql("pg_query", {"query": "DELETE FROM users"}) == "DELETE FROM users"

    @pytest.mark.asyncio
    async def test_generic_adapter_fallback(self) -> None:
        """Falls back to generic adapter for unknown types."""
        hooks = PolicyHooks(
            config=ProxyConfig(),
            policy=PolicyConfig(protective_mode=True),
            target_type="unknown_db",
        )
        assert hooks._extract_sql("query", {"sql": "DELETE FROM users"}) == "DELETE FROM users"
