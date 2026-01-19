# Configuration

Mantora acts as a transparent proxy by default, but you can configure safety rules, session storage paths, and data retention limits using a `config.toml`.

## Configuration File Locations

Mantora searches for `config.toml` in the following order:

1.  **CLI Flag:** `mantora up --config ./my_config.toml`
2.  **Local Directory:** `./config.toml` (in the current working directory)
3.  **User-Global Config:**
    - macOS: `~/Library/Application Support/mantora/config.toml`
    - Linux: `~/.config/mantora/config.toml`
    - Windows: `%APPDATA%\mantora\config.toml`

> **Note:** Mantora does **not** create a config file automatically. If no config is found, it uses sensible defaults (Protective Mode: ON, SQLite storage: `~/.mantora/sessions.db`).

## Example Configuration

```toml
# config.toml

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

[target]
# Mode A: Direct Connector (Mantora runs the MCP server)
type = "duckdb"
command = ["mcp-server-duckdb", "--db", "./demo.duckdb"]
# env = { "KEY" = "VALUE" }

# Mode B: Proxy (Mantora wraps an existing MCP server process)
# [target]
# type = "snowflake"
# command = ["mcp-server-snowflake"]
```

## Session Database (SQLite)

Mantora stores sessions, tool calls, and approvals in a local SQLite database.

*   **Default:** `~/.mantora/sessions.db`
*   **Override:**
    *   `config.toml`: `sqlite_path = "/path/to/db"`
    *   Environment Variable: `MANTORA_STORAGE__SQLITE__PATH`

> **Important:** If you run the UI (`mantora up`) and the MCP proxy (`mantora mcp`) in separate terminals, ensure they point to the **same** database file.

## Environment Variables

Most configuration options can be overridden via environment variables using the `MANTORA_` prefix and double underscores for nesting.

*   `MANTORA_POLICY__PROTECTIVE_MODE=false`
*   `MANTORA_LIMITS__PREVIEW_ROWS=50`
*   `MANTORA_STORAGE__SQLITE__PATH=/tmp/test.db`
