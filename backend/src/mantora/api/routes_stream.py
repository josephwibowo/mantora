from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from mantora.store.interface import SessionStore

router = APIRouter(prefix="/api")


def _get_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.store)


def _encode_sse(*, event: str, data: str) -> bytes:
    return f"event: {event}\ndata: {data}\n\n".encode()


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: UUID, request: Request) -> StreamingResponse:
    store = _get_store(request)

    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    queue = store.get_step_queue(session_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def generator() -> AsyncIterator[bytes]:
        yield b": connected\n\n"

        # We need to track the last seen timestamp (or step count) to poll for new items.
        # However, since we might miss steps that happen *while* connecting if we
        # blindly select "from now", a safer bet is to rely on a high-water mark.
        # But `list_steps` is usually called by the FE on load. So we just need "new" stuff.
        # Let's count current steps as a high-water mark.

        # Get initial high water mark
        existing_steps = store.list_steps(session_id)
        last_seen_count = len(existing_steps)

        while True:
            # Poll interval
            await asyncio.sleep(0.5)

            # Force SQLite to check filesystem for changes (helps with Docker volume sync)
            with suppress(Exception):
                # This is a lightweight op that forces a check of the -wal file
                if hasattr(store, "_conn"):
                    store._conn.execute("PRAGMA schema_version")

            # Check for new steps
            # Ideally we'd have a more efficient way than listing all,
            # but for the SQLite demo this is fine.
            current_steps = store.list_steps(session_id)

            if len(current_steps) > last_seen_count:
                # We have new steps!
                new_items = current_steps[last_seen_count:]
                for step in new_items:
                    payload = json.dumps(step.model_dump(mode="json"), separators=(",", ":"))
                    yield _encode_sse(event="step", data=payload)

                last_seen_count = len(current_steps)
            else:
                yield b": ping\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
