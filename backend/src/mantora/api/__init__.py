"""API utilities and helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mantora.store.interface import SessionStore


def get_store() -> SessionStore:
    """Get the session store from the current FastAPI app context."""
    import inspect

    from starlette.requests import Request

    # Find the Request object in the call stack (injected by FastAPI)
    for frame_info in inspect.stack():
        frame_locals = frame_info.frame.f_locals
        for value in frame_locals.values():
            if isinstance(value, Request):
                from typing import cast

                return cast("SessionStore", value.app.state.store)

    # Fallback: This shouldn't happen in normal API calls
    raise RuntimeError("Unable to access app state.store - not in FastAPI context")
