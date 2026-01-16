"""Tests for proxy query error detection.

The proxy should record a query step as `status="error"` when the DB execution
fails, even if the MCP transport/tool-call succeeded.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from mcp import ClientSession, types

from mantora.config import ProxyConfig, TargetConfig
from mantora.config.settings import PolicyConfig
from mantora.mcp.proxy import MCPProxy, _extract_query_error_message
from mantora.store import MemorySessionStore


class FakeClientSession:
    def __init__(self, *, result: types.CallToolResult):
        self._result = result

    async def call_tool(self, name: str, arguments: dict[str, object]) -> types.CallToolResult:
        return self._result


def _new_proxy(*, target_type: str = "duckdb") -> tuple[MCPProxy, MemorySessionStore, UUID]:
    store = MemorySessionStore()
    config = ProxyConfig(
        policy=PolicyConfig(protective_mode=False),
        target=TargetConfig(type=target_type),
    )
    proxy = MCPProxy(config=config, store=store)
    session_id = UUID(proxy.start_session("test"))
    return proxy, store, session_id


def test_extracts_database_error_from_text_content() -> None:
    result = [
        types.TextContent(
            type="text",
            text=(
                "Database error: Parser Error: Wrong number of arguments provided to DATE function"
            ),
        )
    ]
    assert _extract_query_error_message(result) is not None


def test_extracts_database_error_from_serialized_dict() -> None:
    result = [
        {
            "type": "text",
            "text": "Database error: Catalog Error: Table with name missing does not exist!",
            "annotations": None,
            "meta": None,
        }
    ]
    assert _extract_query_error_message(result) is not None


def test_extracts_database_error_from_json_encoded_text() -> None:
    result = [
        types.TextContent(
            type="text",
            text='{"type":"text","text":"Database error: Parser Error: bad syntax"}',
        )
    ]
    assert _extract_query_error_message(result) is not None


def test_does_not_flag_non_prefixed_database_error_text() -> None:
    result = [
        types.TextContent(type="text", text="This query mentions database error but succeeded")
    ]
    assert _extract_query_error_message(result) is None


@pytest.mark.asyncio
async def test_records_query_step_as_error_when_db_error_in_payload() -> None:
    proxy, store, session_id = _new_proxy()

    proxy._client_session = cast(
        ClientSession,
        FakeClientSession(
            result=types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=(
                            "Database error: Catalog Error: Table with name does_not_exist "
                            "does not exist!"
                        ),
                    )
                ],
                isError=False,
            )
        ),
    )

    await proxy._handle_tool_call("query", {"sql": "select * from does_not_exist"})

    steps = list(store.list_steps(session_id))
    assert len(steps) == 1
    assert steps[0].name == "query"
    assert steps[0].status == "error"


@pytest.mark.asyncio
async def test_records_query_step_as_error_when_rpc_is_error() -> None:
    proxy, store, session_id = _new_proxy()

    proxy._client_session = cast(
        ClientSession,
        FakeClientSession(
            result=types.CallToolResult(
                content=[types.TextContent(type="text", text="some rpc-layer error")],
                isError=True,
            )
        ),
    )

    await proxy._handle_tool_call("query", {"sql": "select 1"})

    steps = list(store.list_steps(session_id))
    assert len(steps) == 1
    assert steps[0].status == "error"
