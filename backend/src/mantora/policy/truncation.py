from __future__ import annotations


def cap_text(text: str, *, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, False

    truncated_raw = raw[:max_bytes]
    truncated_text = truncated_raw.decode("utf-8", errors="ignore")
    return truncated_text, True
