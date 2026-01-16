#!/usr/bin/env python3
"""Run the Mantora MCP proxy.

This script instantiates and runs the MCPProxy, connecting to a target MCP server
(configured via config.toml or command-line arguments) and storing sessions in SQLite.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add src to sys.path to allow running the script directly from any directory
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

from mantora.config import load_proxy_config  # noqa: E402
from mantora.mcp import MCPProxy, PolicyHooks  # noqa: E402
from mantora.store.sqlite import SQLiteSessionStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the proxy server."""
    # Load configuration
    config_path = None
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    config = load_proxy_config(config_path)
    logger.info("Loaded proxy config: %s", config)

    # Create session store
    db_path = config.sqlite_path if config.sqlite_path else Path.home() / ".mantora" / "sessions.db"
    store = SQLiteSessionStore(db_path)
    logger.info("Session store initialized at: %s", store._db_path)

    # Create and run proxy
    hooks = PolicyHooks(
        config=config,
        policy=config.policy,
        limits=config.limits,
        target_type=config.target.type,
    )
    proxy = MCPProxy(config=config, store=store, hooks=hooks)
    logger.info("Starting MCP proxy...")
    try:
        await proxy.run()
    finally:
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
