from __future__ import annotations

from mantora.mcp.trace_sanitizer import (
    REDACTED_EMAIL,
    REDACTED_PROJECT_ID,
    REDACTED_TIMESTAMP,
    REDACTED_TOKEN,
    REDACTED_UUID,
    sanitize_trace_payload,
)


def test_sanitize_trace_payload_redacts_sensitive_values() -> None:
    payload = {
        "email": "alice@example.com",
        "project_id": "real-prod-project-123",
        "token": "ya29.thisIsDefinitelyAToken",
        "created_at": "2026-01-18T00:00:00Z",
        "request_id": "00000000-0000-0000-0000-000000000099",
    }

    sanitized = sanitize_trace_payload(payload)
    assert sanitized["email"] == REDACTED_EMAIL
    assert sanitized["project_id"] == REDACTED_PROJECT_ID
    assert sanitized["token"] == REDACTED_TOKEN
    assert sanitized["created_at"] == REDACTED_TIMESTAMP
    assert sanitized["request_id"] == REDACTED_UUID


def test_sanitize_trace_payload_preserves_sql_strings() -> None:
    payload = {
        "sql": "SELECT DATE '2026-01-01' AS day, 'alice@example.com' AS email",
        "query": "SELECT '2026-01-18T00:00:00Z' AS ts",
    }

    sanitized = sanitize_trace_payload(payload)
    assert sanitized["sql"] == payload["sql"]
    assert sanitized["query"] == payload["query"]


def test_sanitize_trace_payload_sanitizes_json_strings() -> None:
    payload = {
        "result": (
            '{"email":"bob@example.com","ts":"2026-01-18T00:00:00Z",'
            '"id":"00000000-0000-0000-0000-000000000123"}'
        )
    }

    sanitized = sanitize_trace_payload(payload)
    assert REDACTED_EMAIL in sanitized["result"]
    assert REDACTED_TIMESTAMP in sanitized["result"]
    assert REDACTED_UUID in sanitized["result"]
