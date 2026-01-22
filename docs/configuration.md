# Configuration

Mantora acts as a transparent proxy by default.
> **Tip:** You can manage targets entirely via the **Control Room UI** (`mantora up`). File-based configuration is only needed for advanced settings like safety rules, storage paths, or headless environments.

Checks safety rules, session storage paths, and data retention limits using `mantora.toml`.

## Configuration File Locations

### Global Configuration

Mantora searches for `mantora.toml` in the following order:

1.  **CLI Flag:** `mantora up --config ./my-mantora.toml`
2.  **Local Directory:** `./mantora.toml` (in the current working directory)
3.  **User-Global Config:**
    - macOS: `~/Library/Application Support/mantora/mantora.toml`
    - Linux: `~/.config/mantora/mantora.toml`
    - Windows: `%APPDATA%\mantora\mantora.toml`

**Priority Order** (highest to lowest):
1. UI Active Target (from `mantora up`) - **Overrides any file-based target**
2. CLI arguments (`--connector`, `--db`, `--dsn`)
3. Config file (locations listed above)

> **Note:** Mantora does **not** create a config file automatically. If no config is found, it uses sensible defaults (Protective Mode: ON, SQLite storage: `~/.mantora/sessions.db`).

## Example Configuration

```toml
# mantora.toml

# Allowed CORS origins for the UI/API
cors_allow_origins = [
  "http://localhost:3030",
  "http://127.0.0.1:3030",
  "http://localhost:5173",
]

[policy]
protective_mode = true          # Enable safety checks
block_ddl = true                # Block CREATE, ALTER, DROP
block_dml = true                # Block INSERT, UPDATE, DELETE
block_multi_statement = true    # Block multiple SQL statements in one call
block_delete_without_where = true # Block DELETE queries missing a WHERE clause

[limits]
preview_rows = 10               # Number of rows to capture in evidence
preview_bytes = 524288          # Max bytes to capture per result
preview_columns = 80            # Max columns to capture
retention_days = 14             # How long to keep session data
max_db_bytes = 0                # Max size of SQLite DB (0 = disabled)

# Session store database (optional; defaults to ~/.mantora/sessions.db)
sqlite_path = "./data/sessions.db"

# Note: Targets are best managed via the UI, but you can override connection
# settings here if really needed (not recommended for most users).
# [target]
# type = "duckdb"
# command = ...
```



## Session Database (SQLite)

Mantora stores sessions, tool calls, and approvals in a local SQLite database.

*   **Default:** `~/.mantora/sessions.db`
*   **Override:**
    *   `mantora.toml`: `sqlite_path = "/path/to/db"`
    *   Environment Variable: `MANTORA_STORAGE__SQLITE__PATH`

> **Important:** If you run the UI (`mantora up`) and the MCP proxy (`mantora mcp`) in separate terminals, ensure they point to the **same** database file.

## Environment Variables

Most configuration options can be overridden via environment variables using the `MANTORA_` prefix and double underscores for nesting.

*   `MANTORA_POLICY__PROTECTIVE_MODE=false`
*   `MANTORA_LIMITS__PREVIEW_ROWS=50`
*   `MANTORA_STORAGE__SQLITE__PATH=/tmp/test.db`
