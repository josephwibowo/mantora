"""Policy enforcement hooks for MCP proxy.

Per DEC-V0-SAFETY-MODES: protective default, transparent optional.
Per PRI-PROTECTIVE-DEFAULT: protective is default.
Per PRI-HARD-CAPS-ALWAYS: caps are enforced regardless of agent requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp import types

from mantora.config.settings import LimitsConfig, PolicyConfig
from mantora.connectors.interface import Adapter
from mantora.connectors.registry import get_adapter
from mantora.mcp.proxy import ForwardContext, ProxyHooks
from mantora.policy import CapsConfig, cap_preview


@dataclass
class PolicyHooks(ProxyHooks):
    """Proxy hooks that enforce safety mode and caps.

    - pre_forward: Allow (blocking/approval happens in MCPProxy)
    - post_response: Cap preview data before storage/streaming
    """

    policy: PolicyConfig = field(default_factory=PolicyConfig)
    limits: LimitsConfig | None = None
    target_type: str = "generic"

    def _get_adapter(self) -> Adapter:
        """Get the adapter for the configured target type."""
        return get_adapter(self.target_type)

    def _extract_sql(self, tool_name: str, arguments: dict[str, Any]) -> str | None:
        """Extract SQL from tool arguments using the adapter.

        Returns None if no SQL can be extracted.
        """
        adapter = self._get_adapter()
        evidence = adapter.extract_evidence(tool_name, arguments, None)
        return evidence.get("sql")

    async def pre_forward(self, ctx: ForwardContext) -> tuple[bool, str | None]:
        """Allow tool calls; v0 approval blocking is handled in MCPProxy._handle_tool_call()."""
        return (True, None)

    def _get_caps_config(self) -> CapsConfig:
        """Get caps configuration."""
        if self.limits is None:
            return CapsConfig()

        return CapsConfig(
            max_rows=self.limits.preview_rows,
            max_columns=self.limits.preview_columns,
            max_bytes=self.limits.preview_bytes,
        )

    async def post_response(self, ctx: ForwardContext, result: Any) -> Any:
        """Apply caps to response data.

        Caps are always enforced regardless of safety mode.

        Args:
            ctx: Forward context.
            result: The raw result from the target.

        Returns:
            The result with caps applied to content.
        """
        # Handle MCP CallToolResult
        if not hasattr(result, "content"):
            return result

        caps_config = self._get_caps_config()
        capped_content: list[
            types.TextContent
            | types.ImageContent
            | types.AudioContent
            | types.ResourceLink
            | types.EmbeddedResource
        ] = []

        for item in result.content:
            if isinstance(item, types.TextContent):
                # Cap text content
                capped = cap_preview(item.text, config=caps_config)
                text = capped.data

                # Add truncation marker if needed
                if capped.was_truncated:
                    text = f"{text}\n\n[Preview truncated: {capped.truncation_summary}]"

                capped_content.append(types.TextContent(type="text", text=text))
            else:
                # Pass through non-text content unchanged
                capped_content.append(item)

        # Return modified result with capped content
        # Create a new CallToolResult with the capped content
        return types.CallToolResult(content=capped_content, isError=result.isError)
