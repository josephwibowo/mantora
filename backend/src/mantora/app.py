from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mantora.api.routes_casts import router as casts_router
from mantora.api.routes_pending import router as pending_router
from mantora.api.routes_sessions import router as sessions_router
from mantora.api.routes_settings import router as settings_router
from mantora.api.routes_stream import router as stream_router
from mantora.config.settings import Settings, StorageBackend
from mantora.store.memory import MemorySessionStore
from mantora.store.retention import prune_sqlite_sessions
from mantora.store.sqlite import SQLiteSessionStore


def get_bundled_frontend_path() -> Path | None:
    """Resolve bundled frontend assets inside the package."""
    try:
        bundled_root = resources.files("mantora") / "_static"
    except Exception:
        return None

    bundled_path = Path(str(bundled_root))
    if bundled_path.is_dir():
        return bundled_path
    return None


def get_frontend_dist_path() -> Path | None:
    """Locate frontend assets for serving."""
    logger = logging.getLogger("mantora")

    frontend_dist_env = os.environ.get("MANTORA_FRONTEND_DIST")
    if frontend_dist_env:
        env_path = Path(frontend_dist_env)
        if env_path.is_dir():
            return env_path
        logger.warning("MANTORA_FRONTEND_DIST set but path not found: %s", env_path)

    current = Path(__file__).resolve()
    dev_path = current.parents[3] / "frontend" / "dist"
    if dev_path.is_dir():
        return dev_path

    return get_bundled_frontend_path()


def create_app(*, settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Mantora")

    # Set settings first so lifespan can access them
    app.state.settings = settings or Settings()
    logger = logging.getLogger("mantora")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.settings.storage.backend == StorageBackend.memory:
            app.state.store = MemorySessionStore()
        else:
            sqlite_path = app.state.settings.storage.sqlite_path
            retention_days = app.state.settings.limits.retention_days
            max_db_bytes = app.state.settings.limits.max_db_bytes
            store = SQLiteSessionStore(
                sqlite_path,
                retention_days=retention_days,
                max_db_bytes=max_db_bytes,
            )

            if retention_days > 0 or max_db_bytes > 0:
                prune_sqlite_sessions(
                    db_path=sqlite_path,
                    retention_days=retention_days,
                    max_db_bytes=max_db_bytes,
                )

            app.state.store = store

        try:
            yield
        finally:
            store = app.state.store
            if isinstance(store, SQLiteSessionStore):
                store.close()

    app.router.lifespan_context = lifespan

    # Initialize store immediately for testing (TestClient doesn't trigger lifespan)
    if not hasattr(app.state, "store"):
        if app.state.settings.storage.backend == StorageBackend.memory:
            app.state.store = MemorySessionStore()
        else:
            sqlite_path = app.state.settings.storage.sqlite_path
            retention_days = app.state.settings.limits.retention_days
            max_db_bytes = app.state.settings.limits.max_db_bytes
            store = SQLiteSessionStore(
                sqlite_path,
                retention_days=retention_days,
                max_db_bytes=max_db_bytes,
            )

            if retention_days > 0 or max_db_bytes > 0:
                prune_sqlite_sessions(
                    db_path=sqlite_path,
                    retention_days=retention_days,
                    max_db_bytes=max_db_bytes,
                )

            app.state.store = store

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS allowed origins: %s", app.state.settings.cors_allow_origins)

    app.include_router(sessions_router)
    app.include_router(settings_router)
    app.include_router(stream_router)
    app.include_router(casts_router)
    app.include_router(pending_router)

    frontend_dist = get_frontend_dist_path()
    if frontend_dist and frontend_dist.is_dir():
        logger = logging.getLogger("mantora")
        logger.debug("Serving frontend from %s", frontend_dist)

        @app.get("/")
        async def index() -> Any:
            return FileResponse(frontend_dist / "index.html")

        # Mount assets separately to avoid catch-all interference
        if (frontend_dist / "assets").is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(frontend_dist / "assets")),
                name="assets",
            )

        @app.get("/{full_path:path}")
        async def catch_all(full_path: str) -> Any:
            """Catch-all for SPA routing."""
            # If it's an API call that reached here, it's a 404
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")

            # If it's a static file that exists, let StaticFiles handle it
            # (if we had it mounted at root).
            # But since we want SPA routing, we serve index.html for everything else
            return FileResponse(frontend_dist / "index.html")

    return app
