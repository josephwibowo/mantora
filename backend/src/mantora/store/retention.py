from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast


def _db_size_bytes(db_path: Path) -> int:
    try:
        return db_path.stat().st_size
    except FileNotFoundError:
        return 0


def prune_sqlite_sessions(
    *, db_path: Path, retention_days: int, max_db_bytes: int | None = None
) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        pruned = 0
        if retention_days > 0:
            row = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE created_at < ?",
                (cutoff.isoformat(),),
            ).fetchone()
            if row is not None:
                to_prune = cast(int, row[0])
                if to_prune > 0:
                    conn.execute(
                        "DELETE FROM sessions WHERE created_at < ?",
                        (cutoff.isoformat(),),
                    )
                    pruned += to_prune

        pruned_by_size = 0
        if max_db_bytes and max_db_bytes > 0 and _db_size_bytes(db_path) > max_db_bytes:
            while _db_size_bytes(db_path) > max_db_bytes:
                row = conn.execute(
                    "SELECT id FROM sessions ORDER BY created_at ASC LIMIT 1"
                ).fetchone()
                if row is None:
                    break
                session_id = row[0]
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                pruned_by_size += 1

            if pruned_by_size > 0:
                conn.commit()
                conn.execute("VACUUM")

        conn.commit()
        return pruned + pruned_by_size
    finally:
        conn.close()
