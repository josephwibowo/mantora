# Mantora 🛡️

> **The open-source run log for MCP agents.**
> Get a shareable report to verify and reproduce what the agent did — **plus a protective mode for common dangerous SQL.**

[![PyPI](https://img.shields.io/pypi/v/mantora)](https://pypi.org/project/mantora/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

![Mantora UI screenshot](docs/assets/demo.gif)

Mantora focuses on making agent behavior **reviewable and repeatable**. It records the key evidence from each session and turns it into a Markdown report. Protective mode adds basic guardrails (block/warn rules) so you don’t learn about a bad query the hard way.

## What you get
- **🔍 Session Logs:** Capture the exact SQL and tool calls an agent makes for easy verification.
- **🧾 Shareable Reports:** One-click to generate a Markdown summary of the session for Pull Requests or Slack.
- **🛡️ Protective Mode:** Basic guardrails that block or warn on destructive SQL patterns by default.

## Quick Start

### 1. Install
```bash
pipx install "mantora[duckdb,postgres]"
```

### 2. Run the Recorder (UI)

Start the dashboard to see your sessions in real-time:

```bash
mantora up
```

### 3. Connect Your Agent

Configure your MCP client (e.g., `claude_desktop_config.json`) to route through Mantora.

**For DuckDB:**

```json
{
  "mcpServers": {
    "my-db": {
      "command": "mantora",
      "args": ["mcp", "--connector", "duckdb", "--db", "./my_data.db"]
    }
  }
}
```

**For Postgres:**

```json
{
  "mcpServers": {
    "my-db": {
      "command": "mantora",
      "args": [
        "mcp",
        "--connector",
        "postgres",
        "--dsn",
        "postgresql://user:password@localhost:5432/dbname"
      ]
    }
  }
}
```

### How it works

```mermaid
sequenceDiagram
    participant Agent as Claude/Cursor
    participant Mantora as Mantora 🛡️
    participant DB as Postgres/DuckDB

    Agent->>Mantora: "SELECT * FROM users"
    Note over Mantora: 1. Check Safety Policy
    Mantora->>DB: Execute Query
    DB-->>Mantora: Return Rows
    Note over Mantora: 2. Log Report (Async)
    Mantora-->>Agent: Relay Result
```

## Daily Workflow

### 📋 Copy a PR Report

Don't paste messy screenshots. In the Session Summary, click **"Copy for GitHub"**.

* **Result:** A collapsible `<details>` block containing the SQL, execution time, and safety checks. Perfect for Pull Requests.

### 🛑 Review Blocked Mutations

If an agent tries to `DROP TABLE users`, Mantora intercepts it.

* **The Agent sees:** "Error: Action blocked by safety policy."
* **You see:** A red entry in the Mantora UI with the exact SQL that was blocked.

### 📤 Export Evidence

Need to archive a session?

* **Export JSON:** Get the raw trace data.
* **Download Markdown:** Get a readable log of the entire conversation.

## Safety Defaults

Mantora is designed to be **read-only safe** out of the box.

| Action | Default Policy |
| --- | --- |
| `SELECT` | ✅ Allowed |
| `INSERT`, `UPDATE` | ⚠️ Requires Approval (Configurable) |
| `DELETE` (with WHERE) | ⚠️ Requires Approval |
| `DROP`, `TRUNCATE` | 🛑 Blocked |
| `DELETE` (no WHERE) | 🛑 Blocked |

*Want to change this? See [Configuration](docs/configuration.md).*

## Supported Data Stores

* **DuckDB** (Local files, MotherDuck)
* **Postgres** (Direct connection, Supabase, Neon)
* **BigQuery, Snowflake, Databricks** (***Coming Soon***)

*All data is stored locally. See [Privacy](PRIVACY.md) for details.*

## Documentation

* [Configuration Guide](docs/configuration.md) - Flags, ports, and policy overrides.
* [Architecture](docs/architecture.md) - How the proxy internals work.
* [Contributing](CONTRIBUTING.md) - Build setup and testing.

## Community

Found a bug? Have a feature request?

* [Open an Issue](https://github.com/josephwibowo/mantora/issues)
* **Star this repo** ⭐️ if you find it useful!

## License

MIT © [Joseph Wibowo](https://github.com/josephwibowo)
