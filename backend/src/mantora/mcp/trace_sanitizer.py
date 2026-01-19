"""Utilities for sanitizing recorded MCP traces.

Per PRI-NO-CREDENTIAL-MGMT and PIT-LOGGING-SENSITIVE:
- Never persist credentials/tokens/emails in fixtures.
- Preserve SQL text (evidence) where possible.
"""

from __future__ import annotations

import json
import re
from typing import Any

REDACTED_EMAIL = "<redacted_email>"
REDACTED_PROJECT_ID = "<redacted_project_id>"
REDACTED_TIMESTAMP = "<redacted_timestamp>"
REDACTED_TOKEN = "<redacted_token>"
REDACTED_UUID = "<redacted_uuid>"

_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ISO_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b")
_TOKEN_PREFIX_RE = re.compile(
    r"\b(?:"
    r"ya29\.[A-Za-z0-9._-]+|"  # Google OAuth access token
    r"AIza[0-9A-Za-z_-]{20,}|"  # Google API key
    r"sk-[A-Za-z0-9]{20,}|"  # OpenAI-style key
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"  # Slack token
    r"eyJ[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}"  # JWT-ish
    r")\b"
)

_SQL_KEYS = {"sql", "query", "statement", "command"}
_PROJECT_KEYS = {"project", "project_id", "projectid"}


def sanitize_trace_payload(payload: Any) -> Any:
    """Sanitize a JSON-like payload for writing to golden fixtures.

    This function is deterministic and safe to run repeatedly.
    """
    return _sanitize(payload, parent_key=None)


def _sanitize(value: Any, *, parent_key: str | None) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            sanitized[key_str] = _sanitize(item, parent_key=key_str)
        return sanitized

    if isinstance(value, list):
        return [_sanitize(item, parent_key=parent_key) for item in value]

    if isinstance(value, str):
        if parent_key is not None and parent_key.lower() in _SQL_KEYS:
            return value

        if parent_key is not None and parent_key.lower() in _PROJECT_KEYS:
            return REDACTED_PROJECT_ID

        maybe_json = value.strip()
        if maybe_json.startswith(("{", "[")):
            try:
                parsed = json.loads(maybe_json)
            except (TypeError, ValueError):
                parsed = None
            if parsed is not None:
                sanitized_parsed = _sanitize(parsed, parent_key=parent_key)
                return json.dumps(sanitized_parsed, sort_keys=True, indent=2)

        value = _EMAIL_RE.sub(REDACTED_EMAIL, value)
        value = _TOKEN_PREFIX_RE.sub(REDACTED_TOKEN, value)
        value = _ISO_TS_RE.sub(REDACTED_TIMESTAMP, value)
        value = _UUID_RE.sub(REDACTED_UUID, value)
        return value

    return value
