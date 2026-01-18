"""MCP stdio proxy skeleton.

Per DEC-V0-STDIO-ONLY: stdio transport only.
Per DEC-V0-SAFETY-MODES: protective default, transparent optional.

The proxy:
- Runs as an MCP server for the client (Cursor/Windsurf/etc.)
- Spawns the target MCP server as a subprocess
- Forwards JSON-RPC over stdio
- Exposes session lifecycle tools
- Provides hook points for policy (pre_forward) and adapters (post_response)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import JsonValue

from mantora.config import ProxyConfig
from mantora.config.settings import PolicyConfig
from mantora.connectors.registry import get_adapter
from mantora.mcp.tools import CastTools, SessionTools
from mantora.models.events import ObservedStep, TruncatedText
from mantora.policy.allowlist import is_tool_known_safe
from mantora.policy.blocker import PendingDecision, PendingRequest, PendingStatus, blocker_summary
from mantora.policy.sql_guard import SQLGuardResult, SQLWarning, analyze_sql, should_block_sql
from mantora.policy.truncation import cap_text
from mantora.store import SessionStore

logger = logging.getLogger(__name__)

SQL_EXCERPT_CAP_BYTES = 8 * 1024
ERROR_MESSAGE_CAP_BYTES = 2 * 1024


@dataclass
class ForwardContext:
    """Context passed to hook functions."""

    session_id: str | None
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ProxyHooks:
    """Hook points for policy enforcement and response normalization.

    These are extension points for Phase 3/4:
    - pre_forward: Called before forwarding a tool call (policy checks)
    - post_response: Called after receiving response (adapter normalization)
    """

    config: ProxyConfig

    async def pre_forward(self, ctx: ForwardContext) -> tuple[bool, str | None]:
        """Called before forwarding a tool call.

        Args:
            ctx: The forward context with session, tool name, and arguments.

        Returns:
            Tuple of (should_forward, denial_reason).
            If should_forward is False, denial_reason explains why.
        """
        return (True, None)

    async def post_response(self, ctx: ForwardContext, result: Any) -> Any:
        """Called after receiving a response from the target.

        Args:
            ctx: The forward context.
            result: The raw result from the target.

        Returns:
            The (possibly transformed) result.
        """
        return result


@dataclass
class MCPProxy:
    """MCP stdio proxy that forwards requests to a target server."""

    config: ProxyConfig
    store: SessionStore
    hooks: ProxyHooks | None = None

    _session_tools: SessionTools = field(init=False)
    _cast_tools: CastTools = field(init=False)
    _server: Server = field(init=False)
    _client_session: ClientSession | None = field(default=None, init=False)
    _target_tools: list[types.Tool] = field(default_factory=list, init=False)
    _connection_id: UUID = field(init=False)

    # v0: synchronous human approval for risky operations (stored in sqlite for cross-process UI)
    _blocker_timeout_s: float = 300.0

    def __post_init__(self) -> None:
        if self.hooks is None:
            self.hooks = ProxyHooks(config=self.config)
        self._connection_id = uuid4()
        # Default timeout: 30 minutes (1800 seconds)
        # Set to 0 to disable timeout
        timeout_seconds = 1800.0
        self._session_tools = SessionTools(
            self.store, connection_id=self._connection_id, timeout_seconds=timeout_seconds
        )
        self._cast_tools = CastTools(self.store, self._session_tools)
        self._server = Server("mantora-proxy")
        self._register_handlers()

    def start_session(self, title: str | None = None) -> str:
        """Start a session ahead of the first tool call."""
        return self._session_tools.session_start(title=title, connection_id=self._connection_id)

    def _extract_sql_argument(self, *, tool_name: str, arguments: dict[str, Any]) -> str | None:
        """Extract SQL from a tool call using the configured adapter.

        Avoids brittle assumptions about argument key names (e.g., "sql" vs "query").
        """
        adapter = get_adapter(self.config.target.type or "generic")
        evidence = adapter.extract_evidence(tool_name, arguments, None)
        raw_sql = evidence.get("sql")
        if raw_sql is None:
            return None
        if isinstance(raw_sql, str):
            return raw_sql
        return str(raw_sql)

    def _register_handlers(self) -> None:
        """Register MCP server handlers."""

        @self._server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
        async def list_tools() -> list[types.Tool]:
            return self._get_all_tools()

        @self._server.call_tool()  # type: ignore[untyped-decorator]
        async def call_tool(
            name: str, arguments: dict[str, Any] | None
        ) -> Sequence[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            return await self._handle_tool_call(name, arguments or {})

    def _get_session_tool_definitions(self) -> list[types.Tool]:
        """Get tool definitions for session lifecycle and cast tools."""
        return [
            types.Tool(
                name="session_start",
                description="Start a new observation session. Call at the start of a task.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Optional title for the session",
                        }
                    },
                },
            ),
            types.Tool(
                name="session_end",
                description="End the current observation session.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session ID to end",
                        }
                    },
                    "required": ["session_id"],
                },
            ),
            types.Tool(
                name="session_current",
                description="Get the current session ID.",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="cast_table",
                description="Create a table cast artifact from query results.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title for the table"},
                        "sql": {
                            "type": "string",
                            "description": "SQL query that produced the data",
                        },
                        "rows": {
                            "type": "array",
                            "description": "Data rows as array of objects",
                            "items": {"type": "object"},
                        },
                        "origin_step_id": {
                            "type": "string",
                            "description": "Optional step ID for evidence linkage",
                        },
                        "columns": {
                            "type": "array",
                            "description": "Optional column schema",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                                "required": ["name"],
                            },
                        },
                    },
                    "required": ["title", "sql", "rows"],
                },
            ),
        ]

    def _get_all_tools(self) -> list[types.Tool]:
        """Get all available tools (session + target)."""
        return self._get_session_tool_definitions() + self._target_tools

    async def _handle_session_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[types.TextContent]:
        """Handle session lifecycle tool calls."""
        if name == "session_start":
            session_id = self._session_tools.session_start(
                arguments.get("title"), connection_id=self._connection_id
            )
            return [types.TextContent(type="text", text=f"Session started: {session_id}")]

        if name == "session_end":
            session_id = arguments.get("session_id", "")
            ended = self._session_tools.session_end(session_id, connection_id=self._connection_id)
            if ended:
                return [types.TextContent(type="text", text=f"Session ended: {session_id}")]
            return [types.TextContent(type="text", text="Session not found or not current")]

        if name == "session_current":
            current = self._session_tools.session_current(connection_id=self._connection_id)
            if current:
                return [types.TextContent(type="text", text=f"Current session: {current}")]
            return [types.TextContent(type="text", text="No active session")]

        return [types.TextContent(type="text", text=f"Unknown session tool: {name}")]

    async def _handle_cast_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[types.TextContent]:
        """Handle cast tool calls."""

        if name == "cast_table":
            result = self._cast_tools.cast_table(
                title=arguments["title"],
                sql=arguments["sql"],
                rows=arguments["rows"],
                origin_step_id=arguments.get("origin_step_id"),
                columns=arguments.get("columns"),
                connection_id=self._connection_id,
            )
            return [types.TextContent(type="text", text=json.dumps(result))]

        return [types.TextContent(type="text", text=f"Unknown cast tool: {name}")]

    async def _handle_tool_call(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle a tool call, routing to session tools or forwarding to target.

        Per DEC-V0-SAFETY-MODES: in protective mode, CRITICAL SQL blocks and requires approval.
        Blocking is synchronous from the agent's perspective: we do not return until decided.
        """
        start_time = time.perf_counter()
        step_id = uuid4()  # Pre-allocate ID to link artifacts (like casts) to this step
        cast_result: dict[str, Any] | None = None
        rpc_is_error = False

        try:
            if name in ("session_start", "session_end", "session_current"):
                result: Sequence[
                    types.TextContent | types.ImageContent | types.EmbeddedResource
                ] = await self._handle_session_tool(name, arguments)
            elif name == "cast_table":
                # Inject origin_step_id so the cast links to this step
                arguments["origin_step_id"] = str(step_id)

                cast_result = self._cast_tools.cast_table(
                    title=arguments["title"],
                    sql=arguments["sql"],
                    rows=arguments["rows"],
                    origin_step_id=arguments.get("origin_step_id"),
                    columns=arguments.get("columns"),
                    connection_id=self._connection_id,
                )
                result = [types.TextContent(type="text", text=json.dumps(cast_result))]
            else:
                # Ensure session exists for forwarded calls
                self._session_tools.ensure_session(connection_id=self._connection_id)

                # Build forward context
                ctx = ForwardContext(
                    session_id=self._session_tools.session_current(
                        connection_id=self._connection_id
                    ),
                    tool_name=name,
                    arguments=arguments,
                )

                # v0 blocker flow (query-like tools; key names vary by target server)
                if self.config.policy.protective_mode:
                    adapter = get_adapter(self.config.target.type or "generic")
                    if not is_tool_known_safe(
                        name, adapter, arguments=arguments, policy=self.config.policy
                    ):
                        approval_response = await self._require_approval_for_unknown_tool(
                            name, arguments
                        )
                        if approval_response is not None:
                            return approval_response
                    sql = self._extract_sql_argument(tool_name=name, arguments=arguments)
                    blocker_response = await self._handle_protective_mode_check(
                        name=name, arguments=arguments, sql=sql
                    )
                    if blocker_response is not None:
                        return blocker_response

                # Pre-forward hook (policy check)
                if self.hooks:
                    should_forward, denial_reason = await self.hooks.pre_forward(ctx)
                    if not should_forward:
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Tool call denied: {denial_reason or 'policy violation'}",
                            )
                        ]

                # Forward to target
                if self._client_session is None:
                    return [types.TextContent(type="text", text="Target server not connected")]

                target_result = await self._client_session.call_tool(name, arguments)
                rpc_is_error = bool(getattr(target_result, "isError", False))

                # Post-response hook (adapter normalization)
                if self.hooks:
                    target_result = await self.hooks.post_response(ctx, target_result)
                    rpc_is_error = bool(getattr(target_result, "isError", False))

                # Extract content
                result = cast(
                    Sequence[types.TextContent | types.ImageContent | types.EmbeddedResource],
                    target_result.content,
                )

            # Record step (if not a session lifecycle tool)
            if name not in ("session_start", "session_end", "session_current"):
                if name == "cast_table" and cast_result is not None:
                    recorded_args = _redact_cast_table_args(arguments)
                    recorded_result: Any = cast_result
                else:
                    recorded_args = arguments
                    recorded_result = result
                self._record_step(
                    name=name,
                    args=recorded_args,
                    result=recorded_result,
                    status="error" if rpc_is_error else "ok",
                    duration_ms=int((time.perf_counter() - start_time) * 1000),
                    step_id=step_id,
                )

            return result

        except Exception as e:
            logger.error("Error handling tool call %s: %s", name, e, exc_info=True)
            if name not in ("session_start", "session_end", "session_current"):
                self._record_step(
                    name=name,
                    args=arguments,
                    result={"error": str(e)},
                    status="error",
                    duration_ms=int((time.perf_counter() - start_time) * 1000),
                    step_id=step_id,
                )
            raise

    def _record_step(
        self,
        name: str,
        args: dict[str, Any],
        result: Any,
        duration_ms: int,
        status: Literal["ok", "error"] = "ok",
        step_id: UUID | None = None,
    ) -> None:
        """Record a tool call as a step in the session."""
        session_id_str = self._session_tools.session_current(connection_id=self._connection_id)
        if not session_id_str:
            return

        session_id = UUID(session_id_str)

        adapter = get_adapter(self.config.target.type or "generic")
        target_type = adapter.target_type
        category = "cast" if name == "cast_table" else adapter.categorize_tool(name)

        # Receipt/trace v1 fields (optional)
        sql: TruncatedText | None = None
        sql_classification: str | None = None
        risk_level: str | None = None
        warnings: list[str] | None = None
        error_message: str | None = None
        result_rows_shown: int | None = None
        result_rows_total: int | None = None
        captured_bytes: int | None = None

        if category == "cast" and isinstance(result, dict):
            rows_shown = result.get("rows_shown")
            total_rows = result.get("total_rows")
            if isinstance(rows_shown, int):
                result_rows_shown = rows_shown
            if isinstance(total_rows, int):
                result_rows_total = total_rows

        sql_for_analysis: str | None = None
        if name == "cast_table":
            if isinstance(args.get("sql"), str):
                sql_for_analysis = args["sql"]
        else:
            if category == "query":
                sql_for_analysis = self._extract_sql_argument(tool_name=name, arguments=args)

        if sql_for_analysis:
            sql_text, sql_truncated = cap_text(sql_for_analysis, max_bytes=SQL_EXCERPT_CAP_BYTES)
            sql = TruncatedText(text=sql_text, truncated=sql_truncated)

            guard_result = analyze_sql(sql_for_analysis)
            sql_classification = guard_result.classification.value
            risk_level = guard_result.risk_level.value
            if guard_result.warnings:
                warnings = [w.value for w in guard_result.warnings]

        # Create preview text from result

        # Serialize result if it contains Pydantic models (like TextContent)
        serialized_result = result
        if isinstance(result, list | tuple):
            serialized_list = []
            for item in result:
                if hasattr(item, "model_dump"):
                    serialized_list.append(item.model_dump())
                elif hasattr(item, "dict"):
                    serialized_list.append(item.dict())
                else:
                    serialized_list.append(item)
            serialized_result = serialized_list

        try:
            res_str = json.dumps(serialized_result)
        except (TypeError, ValueError):
            res_str = str(serialized_result)

        capped, truncated = cap_text(res_str, max_bytes=1024)  # Use 1KB for preview

        if category == "query":
            extracted_error = _extract_query_error_message(result)
            if extracted_error:
                capped_error, _ = cap_text(extracted_error, max_bytes=ERROR_MESSAGE_CAP_BYTES)
                error_message = capped_error
                status = "error"

        if status == "error" and error_message is None:
            extracted_error = _extract_query_error_message(result)
            if extracted_error:
                capped_error, _ = cap_text(extracted_error, max_bytes=ERROR_MESSAGE_CAP_BYTES)
                error_message = capped_error

        captured_bytes = len(capped.encode("utf-8"))
        if sql is not None:
            captured_bytes += len(sql.text.encode("utf-8"))
        if error_message is not None:
            captured_bytes += len(error_message.encode("utf-8"))

        stepped_step_id = step_id or uuid4()

        step = ObservedStep(
            id=stepped_step_id,
            session_id=session_id,
            created_at=datetime.now(UTC),
            kind="tool_call",
            name=name,
            status=status,
            duration_ms=duration_ms,
            summary=_compute_step_summary(name=name, status=status),
            risk_level=risk_level,
            warnings=warnings,
            target_type=target_type,
            tool_category=category if category != "session" else None,
            sql=sql,
            sql_classification=sql_classification,
            result_rows_shown=result_rows_shown,
            result_rows_total=result_rows_total,
            captured_bytes=captured_bytes,
            error_message=error_message,
            args=args,
            result=(
                serialized_result
                if isinstance(serialized_result, dict | list | str | int | float | bool)
                else None
            ),
            preview=TruncatedText(text=capped, truncated=truncated),
        )

        self._store_step(step)

    def _store_step(self, step: ObservedStep) -> None:
        """Store a step, auto-creating a session if needed.

        If the session doesn't exist (KeyError), creates a new session and retries once.
        This prevents silent tracking failures while maintaining robustness.
        """
        try:
            self.store.add_step(step)
        except KeyError:
            # Session doesn't exist - create a new one and retry
            logger.warning(
                "Step session %s not found, creating new session and retrying", step.session_id
            )
            try:
                # Force create a new session
                new_session_id = UUID(
                    self._session_tools.session_start(
                        title="Recovered Session", connection_id=self._connection_id
                    )
                )

                # Update step with new session ID
                step = ObservedStep(
                    **step.model_dump(exclude={"session_id"}), session_id=new_session_id
                )

                # Retry with new session
                self.store.add_step(step)
                logger.info("Successfully stored step in recovered session %s", new_session_id)
            except Exception as e:
                # Critical: tracking failed even after recovery attempt
                logger.error(
                    "CRITICAL: Failed to record step even after session recovery: %s",
                    e,
                    exc_info=True,
                )
        except Exception as e:
            logger.error("Failed to record step: %s", e, exc_info=True)

    async def _handle_protective_mode_check(
        self, *, name: str, arguments: dict[str, Any], sql: str | None
    ) -> Sequence[types.TextContent] | None:
        """Apply protective mode policy checks for SQL-based tool calls.

        Security: Checks SQL content regardless of tool categorization to prevent
        bypass via unrecognized tool names (e.g., 'query:mantora' vs 'query').

        Args:
            name: Tool name being called.
            arguments: Tool call arguments.
            sql: Extracted SQL query, if any.

        Returns:
            Denial response if blocked, None if allowed to proceed.
        """
        if not sql:
            return None

        # NOTE: We intentionally do NOT check tool category here.
        # Previously this only blocked tools categorized as "query", which allowed
        # agents to bypass protections using unrecognized tool names.

        should_block, reason = should_block_sql(sql, policy=self.config.policy)
        if not should_block:
            return None

        # Create pending request for cross-process UI approval
        pending_id = uuid4()
        guard = analyze_sql(sql)
        policy_rule_ids = _derive_policy_rule_ids_from_sql_guard(
            guard=guard, policy=self.config.policy
        )

        session_id_str = self._session_tools.session_current(connection_id=self._connection_id)
        if session_id_str is None:
            return [types.TextContent(type="text", text="No active session")]

        pending = self.store.create_pending_request(
            request_id=pending_id,
            session_id=UUID(session_id_str),
            tool_name=name,
            arguments={"sql": _cap_for_step_args(sql)},
            classification=guard.classification.value,
            risk_level=guard.risk_level.value,
            reason=reason or guard.reason,
            blocker_step_id=None,
        )

        adapter = get_adapter(self.config.target.type or "generic")
        target_type = adapter.target_type
        category = adapter.categorize_tool(name)
        tool_category = "query" if sql else category

        sql_text, sql_truncated = cap_text(sql, max_bytes=SQL_EXCERPT_CAP_BYTES)
        sql_excerpt = TruncatedText(text=sql_text, truncated=sql_truncated)

        # Record a blocker step for UI + export
        blocker_step = ObservedStep(
            id=uuid4(),
            session_id=UUID(session_id_str),
            created_at=datetime.now(UTC),
            kind="blocker",
            name=name,
            status="ok",
            duration_ms=None,
            summary=f"Blocked: {pending.reason or 'High-risk SQL'}",
            risk_level=pending.risk_level,
            warnings=[w.value for w in guard.warnings] if guard.warnings else None,
            target_type=target_type,
            tool_category=tool_category if tool_category != "session" else None,
            sql=sql_excerpt,
            sql_classification=guard.classification.value,
            policy_rule_ids=policy_rule_ids,
            decision="pending",
            captured_bytes=len(sql_excerpt.text.encode("utf-8")),
            args={
                "request_id": str(pending.id),
                "sql": (
                    pending.arguments.get("sql") if isinstance(pending.arguments, dict) else None
                ),
                "reason": pending.reason,
                "classification": pending.classification,
                "risk_level": pending.risk_level,
                "policy_rule_ids": cast(JsonValue, policy_rule_ids),
            },
            result=None,
            preview=None,
        )
        self._store_step(blocker_step)

        # Wait for decision (or timeout -> auto-deny)
        decided = await self._await_pending_decision(pending.id)
        decision = (
            PendingDecision.allowed
            if decided.status == PendingStatus.allowed
            else PendingDecision.timeout
            if decided.status == PendingStatus.timeout
            else PendingDecision.denied
        )

        # Update the blocker step with the decision
        self.store.update_step(
            blocker_step.id,
            summary=blocker_summary(tool_name=name, decision=decision),
            args={"decision": decision.value},
        )

        if decision != PendingDecision.allowed:
            denial_reason = pending.reason or "High-risk operation"

            if decision == PendingDecision.timeout:
                message = (
                    f"⏳ TIMEOUT: The user did not approve this action in time.\n"
                    f"Reason: {denial_reason}\n"
                    f"STOP: Do not retry this operation automatically. Ask the user for guidance."
                )
            else:
                message = (
                    f"⛔ BLOCKED: This action was explicitly denied by the user.\n"
                    f"Reason: {denial_reason}\n"
                    f"STOP: You MUST NOT retry this operation. It is forbidden."
                )

            return [
                types.TextContent(
                    type="text",
                    text=message,
                )
            ]

        return None

    async def _require_approval_for_unknown_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[types.TextContent] | None:
        """Require explicit approval for unknown tools in protective mode."""
        session_id_str = self._session_tools.session_current(connection_id=self._connection_id)
        if session_id_str is None:
            return [types.TextContent(type="text", text="No active session")]

        pending_id = uuid4()
        reason = "Unknown tool; requires approval in protective mode."
        summarized_args = _summarize_unknown_tool_args(arguments)

        pending = self.store.create_pending_request(
            request_id=pending_id,
            session_id=UUID(session_id_str),
            tool_name=name,
            arguments=summarized_args if summarized_args else None,
            classification="unknown",
            risk_level="unknown",
            reason=reason,
            blocker_step_id=None,
        )

        adapter = get_adapter(self.config.target.type or "generic")
        target_type = adapter.target_type
        category = adapter.categorize_tool(name)
        policy_rule_ids = ["unknown_tool_requires_approval"]

        blocker_step = ObservedStep(
            id=uuid4(),
            session_id=UUID(session_id_str),
            created_at=datetime.now(UTC),
            kind="blocker",
            name=name,
            status="ok",
            duration_ms=None,
            summary=f"Blocked: {reason}",
            risk_level=pending.risk_level,
            target_type=target_type,
            tool_category=category if category != "session" else None,
            policy_rule_ids=policy_rule_ids,
            decision="pending",
            args={
                "request_id": str(pending.id),
                "reason": pending.reason,
                "tool_name": name,
                "policy_rule_ids": cast(JsonValue, policy_rule_ids),
            },
            result=None,
            preview=None,
        )
        self._store_step(blocker_step)

        decided = await self._await_pending_decision(pending.id)
        decision = (
            PendingDecision.allowed
            if decided.status == PendingStatus.allowed
            else PendingDecision.timeout
            if decided.status == PendingStatus.timeout
            else PendingDecision.denied
        )

        self.store.update_step(
            blocker_step.id,
            summary=blocker_summary(tool_name=name, decision=decision),
            args={"decision": decision.value},
        )

        if decision != PendingDecision.allowed:
            if decision == PendingDecision.timeout:
                message = (
                    "⏳ TIMEOUT: The user did not approve this action in time.\n"
                    f"Reason: {reason}\n"
                    "STOP: Do not retry this operation automatically. Ask the user for guidance."
                )
            else:
                message = (
                    "⛔ BLOCKED: This action was explicitly denied by the user.\n"
                    f"Reason: {reason}\n"
                    "STOP: You MUST NOT retry this operation. It is forbidden."
                )

            return [types.TextContent(type="text", text=message)]

        return None

    async def _await_pending_decision(self, request_id: UUID) -> PendingRequest:
        """Poll the store until a pending request is decided or times out."""
        deadline = time.monotonic() + self._blocker_timeout_s
        while True:
            pending = self.store.get_pending_request(request_id)
            if pending is None:
                session_id_str = self._session_tools.session_current(
                    connection_id=self._connection_id
                )
                if session_id_str is None:
                    raise RuntimeError(
                        "Pending request disappeared and no active session is available"
                    )
                # Treat missing pending as denied (best-effort).
                return PendingRequest(
                    id=request_id,
                    session_id=UUID(session_id_str),
                    created_at=datetime.now(UTC),
                    tool_name="query",
                    arguments=None,
                    classification=None,
                    risk_level=None,
                    reason="Pending request disappeared",
                    blocker_step_id=None,
                    status=PendingStatus.denied,
                    decided_at=datetime.now(UTC),
                )

            if pending.status != PendingStatus.pending:
                return pending

            if time.monotonic() >= deadline:
                decided = self.store.decide_pending_request(
                    request_id, status=PendingStatus.timeout
                )
                if decided is None:
                    return pending
                return decided

            await asyncio.sleep(0.25)

    async def _fetch_target_tools(self) -> None:
        """Fetch available tools from the target server."""
        if self._client_session is None:
            return

        result = await self._client_session.list_tools()
        self._target_tools = list(result.tools)
        logger.info("Fetched %d tools from target", len(self._target_tools))

    @asynccontextmanager
    async def _target_connection(self) -> AsyncIterator[None]:
        """Context manager for target server connection.

        Follows the official MCP SDK pattern:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
        """
        if not self.config.target.command:
            logger.warning("No target command configured, running without target")
            yield
            return

        params = StdioServerParameters(
            command=self.config.target.command[0],
            args=self.config.target.command[1:] if len(self.config.target.command) > 1 else [],
            env=self.config.target.env if self.config.target.env else None,
        )

        # Use nested async with per official MCP SDK pattern
        async with stdio_client(params) as (read, write):  # noqa: SIM117
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Store reference for use by tool handlers
                self._client_session = session

                # Fetch available tools from target
                await self._fetch_target_tools()

                logger.info("Successfully connected to target server")

                try:
                    yield
                finally:
                    # Clean up state when exiting
                    self._client_session = None
                    self._target_tools = []

    async def run(self) -> None:
        """Run the proxy server."""
        async with self._target_connection(), stdio_server() as (read, write):
            await self._server.run(read, write, self._server.create_initialization_options())


def _compute_step_summary(*, name: str, status: Literal["ok", "error"]) -> str:
    if status == "error":
        return f"{name} failed"
    return f"{name}"


def _extract_query_error_message(result: Any) -> str | None:
    for payload in _iter_payloads(result):
        message = _extract_error_message(payload)
        if message:
            return message
    return None


def _iter_payloads(result: Any) -> Sequence[Any]:
    if isinstance(result, list | tuple):
        return result
    return (result,)


def _extract_error_message(payload: Any) -> str | None:
    if payload is None:
        return None

    if isinstance(payload, str):
        return _extract_error_from_text(payload)

    if isinstance(payload, dict):
        message = _extract_error_from_value(payload.get("error"))
        if message:
            return message
        message = _extract_error_from_value(payload.get("errors"))
        if message:
            return message
        text = payload.get("text")
        if isinstance(text, str):
            return _extract_error_from_text(text)
        return None

    text = getattr(payload, "text", None)
    if isinstance(text, str):
        return _extract_error_from_text(text)

    return None


def _extract_error_from_text(text: str) -> str | None:
    trimmed = text.strip()
    if not trimmed:
        return None
    if trimmed.startswith(("{", "[")):
        try:
            parsed = json.loads(trimmed)
        except (TypeError, ValueError):
            return None
        return _extract_error_message(parsed)
    if trimmed.lower().startswith("database error"):
        return trimmed
    return None


def _extract_error_from_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str):
            return message.strip() or None
    if isinstance(value, list):
        for item in value:
            message = _extract_error_from_value(item)
            if message:
                return message
    return None


def _cap_for_step_args(text: str) -> str:
    # v0: keep args bounded even if the agent sends very large SQL.
    capped, truncated = cap_text(text, max_bytes=8 * 1024)
    if truncated:
        return capped + "\n-- [truncated]"
    return capped


def _summarize_unknown_tool_args(arguments: dict[str, Any]) -> dict[str, Any]:
    """Summarize unknown tool arguments without storing full payloads."""
    summarized: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str | int | float | bool):
            text_value = str(value)
            summarized[key] = text_value if len(text_value) <= 120 else "<omitted>"
        elif isinstance(value, list):
            summarized[key] = f"<list len={len(value)}>"
        elif isinstance(value, dict):
            summarized[key] = f"<object keys={len(value)}>"
        else:
            summarized[key] = f"<{type(value).__name__}>"
    return summarized


def _redact_cast_table_args(args: dict[str, Any]) -> dict[str, Any]:
    """Redact potentially large/sensitive cast payloads before persisting steps.

    The cast artifact itself is stored separately with hard caps applied, so the step
    should only retain lightweight evidence fields (title/sql/ids) and not full rows.
    """
    redacted = dict(args)
    if "rows" not in redacted:
        return redacted

    rows = redacted.get("rows")
    if isinstance(rows, list):
        redacted["rows"] = f"<omitted {len(rows)} rows>"
    else:
        redacted["rows"] = "<omitted>"
    return redacted


def _derive_policy_rule_ids_from_sql_guard(
    *, guard: SQLGuardResult, policy: PolicyConfig
) -> list[str]:
    """Derive policy rule ids fired for a blocked SQL statement.

    Uses coarse-grained rule IDs that are safe to persist/export.
    """
    warnings = set(guard.warnings)

    rule_ids: list[str] = []

    if SQLWarning.MULTI_STATEMENT in warnings and policy.block_multi_statement:
        rule_ids.append("block_multi_statement")
    if SQLWarning.DELETE_NO_WHERE in warnings and policy.block_delete_without_where:
        rule_ids.append("block_delete_without_where")
    if SQLWarning.DDL in warnings and policy.block_ddl:
        rule_ids.append("block_ddl")
    if SQLWarning.DML in warnings and policy.block_dml:
        rule_ids.append("block_dml")

    # Fallback for blocked operations that don't map cleanly to a toggle.
    if not rule_ids:
        rule_ids.append("block_destructive")

    return rule_ids
