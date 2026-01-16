#!/usr/bin/env python3
"""Setup dummy data for local testing.

This script generates three distinct demo sessions to showcase Mantora v0 features:
1. Compliance & Safety: Blocker Modal and SQL Warnings
2. Supply Chain Audit: Smart Tables and Summary Cards
3. Strategy Sync: Evidence Trails and Markdown Export
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

UTC = UTC

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mantora.casts.models import SchemaColumn, TableCast  # noqa: E402
from mantora.config import ProxyConfig  # noqa: E402
from mantora.mcp import MCPProxy  # noqa: E402
from mantora.models.events import ObservedStep, TruncatedText  # noqa: E402
from mantora.store.sqlite import SQLiteSessionStore  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_compliance_session(proxy: MCPProxy) -> None:
    """Session 1: Showcases Blocker Modal and SQL Warnings."""
    logger.info("Creating 'Compliance & Safety' session...")

    session_id_str = proxy._session_tools.session_start("Compliance & Safety Audit")
    session_id = UUID(session_id_str)

    # Step 1: Broad SELECT (Warning: NO_LIMIT)
    logger.info("  - Step 1: Broad query warning")
    sql_star = "SELECT * FROM user_access_logs"
    step_star = ObservedStep(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        duration_ms=210,
        args={"sql": sql_star},
        result={"affected_rows": 1000},
        preview=TruncatedText(text=sql_star, truncated=False),
        risk_level="medium",
        warnings=["NO_LIMIT", "SELECT_STAR"],
    )
    proxy.store.add_step(step_star)

    # Step 2: Dangerous DELETE (Blocked)
    logger.info("  - Step 2: Blocker modal")
    sql_delete = "DELETE FROM production_users"  # No WHERE clause
    step_delete = ObservedStep(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="error",
        duration_ms=4500,  # Long duration implies user waiting
        args={"sql": sql_delete},
        result={"error": "Operation denied by user policy"},
        preview=TruncatedText(text=sql_delete, truncated=False),
        risk_level="critical",
        warnings=["DELETE_NO_WHERE", "DML"],
    )
    # Add a blocker entry for this step (implies it was blocked)
    proxy.store.add_step(step_delete)


async def create_audit_session(proxy: MCPProxy) -> None:
    """Session 2: Showcases Smart Tables and Summary Cards."""
    logger.info("Creating 'Supply Chain Audit' session...")

    session_id_str = proxy._session_tools.session_start("Supply Chain Revenue Audit")
    session_id = UUID(session_id_str)

    # Step 1: List Tables (Low risk)
    step_list = ObservedStep(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="list_tables",
        status="ok",
        duration_ms=45,
        args={},
        result={"tables": ["sales_daily", "inventory", "shipping_logs"]},
        preview=TruncatedText(text="Listing database tables...", truncated=False),
    )
    proxy.store.add_step(step_list)

    # Step 2: Large Query (Truncated, uses Smart Table features)
    logger.info("  - Step 2: Large table cast")
    sql_large = "SELECT * FROM sales_daily ORDER BY day DESC"

    # Generate mock result data (subset of what mock server would return)
    columns = [
        SchemaColumn(name="day", type="date"),
        SchemaColumn(name="region", type="string"),
        SchemaColumn(name="revenue", type="float"),
    ]

    # Create 500 rows
    rows = []
    regions = ["East", "West", "North", "South"]
    for i in range(500):
        rows.append(
            {
                "day": f"2026-01-{i % 30 + 1:02d}",
                "region": regions[i % 4],
                "revenue": 1000.0 + (i * 10),
            }
        )

    step_query = ObservedStep(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        duration_ms=850,
        args={"sql": sql_large},
        result={"row_count": 500},  # Proxy would usually store limited result
        preview=TruncatedText(text=sql_large, truncated=False),
        risk_level="low",
        warnings=[],
    )
    proxy.store.add_step(step_query)

    # Create the Cast artifact linked to this step
    # Emulate truncation (only store first 200 in DB for this demo script,
    # generally proxy handles this)
    stored_rows = rows[:200]

    cast = TableCast(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        origin_step_id=step_query.id,
        title="Daily Sales Revenue (All Regions)",
        sql=sql_large,
        rows=stored_rows,
        columns=columns,
        total_rows=500,
        truncated=True,
    )
    proxy.store.add_cast(cast)


async def create_strategy_session(proxy: MCPProxy) -> None:
    """Session 3: Showcases Export and Evidence Trails."""
    logger.info("Creating 'Strategy Sync' session...")

    session_id_str = proxy._session_tools.session_start("Q1 Strategy Synchronization")
    session_id = UUID(session_id_str)

    # Step 1: Initial Context
    step_note = ObservedStep(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        kind="note",
        name="user",
        status="ok",
        duration_ms=0,
        args={"content": "Analyze the Q1 performance drops in the North region vs priors."},
        result=None,
        preview=TruncatedText(text="Analyze Q1 performance...", truncated=False),
    )
    proxy.store.add_step(step_note)

    # Step 2: Comparative Query
    sql_comp = """
    SELECT region, SUM(revenue) as total, 
           LAG(SUM(revenue)) OVER (PARTITION BY region ORDER BY month) as prior_month
    FROM sales_monthly
    WHERE region = 'North'
    GROUP BY region, month
    """

    step_comp = ObservedStep(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        kind="tool_call",
        name="query",
        status="ok",
        duration_ms=320,
        args={"sql": sql_comp},
        result={"rows": [{"region": "North", "total": 45000, "prior_month": 52000}]},
        preview=TruncatedText(text=sql_comp, truncated=False),
    )
    proxy.store.add_step(step_comp)

    # Step 3: Cast Result
    cast = TableCast(
        id=uuid4(),
        session_id=session_id,
        created_at=datetime.now(UTC),
        origin_step_id=step_comp.id,
        title="North Region Month-over-Month",
        sql=sql_comp,
        rows=[
            {
                "region": "North",
                "month": "2026-03",
                "total": 45000,
                "prior_month": 52000,
                "delta": -13.5,
            }
        ],
        columns=[
            SchemaColumn(name="region", type="string"),
            SchemaColumn(name="month", type="string"),
            SchemaColumn(name="total", type="integer"),
            SchemaColumn(name="prior_month", type="integer"),
            SchemaColumn(name="delta", type="float"),
        ],
        total_rows=1,
        truncated=False,
    )
    proxy.store.add_cast(cast)


async def main() -> None:
    """Run the dummy data setup."""
    logger.info("Setting up detailed demo data for Mantora v0...")

    # Use shared SQLite path (relative to repo root)
    repo_root = Path(__file__).parent.parent.parent
    db_path = repo_root / "data" / "sessions.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Optional: Clean existing DB for fresh demo
    # if db_path.exists():
    #     db_path.unlink()

    store = SQLiteSessionStore(db_path)
    logger.info("Using session store at: %s", db_path)

    # Create proxy (just to use its session tools and store access)
    config = ProxyConfig()
    proxy = MCPProxy(config=config, store=store)

    try:
        await create_compliance_session(proxy)
        await create_audit_session(proxy)
        await create_strategy_session(proxy)

        logger.info("✅ Demo data setup complete!")
        logger.info("Created 3 sessions showcasing new v0 features.")
    finally:
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
