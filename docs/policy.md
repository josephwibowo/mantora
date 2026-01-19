# Policy & Safety

Mantora includes a policy engine designed to be safe by default ("Protective Mode"). It intercepts SQL queries and blocks potentially dangerous operations unless explicitly allowed by the user.

## Protective Mode

When `policy.protective_mode` is `true` (default), Mantora classifies every SQL statement and enforces the following rules.

### Blocked Operations

By default, the following are **blocked** in protective mode:

1.  **DDL (Data Definition Language):**
    *   `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `REINDEX`, `VACUUM`
    *   *Why:* Structural changes should usually happen via migrations, not AI agents.

2.  **DML (Data Manipulation Language):**
    *   `INSERT`, `UPDATE`, `DELETE`, `MERGE`
    *   *Why:* Modifying data can lead to data loss or corruption.

3.  **Unsafe Patterns:**
    *   **DELETE without WHERE:** Prevents accidental deletion of all rows.
    *   **Multi-statement SQL:** Prevents injection attacks or hiding destructive commands after a harmless SELECT.

### Warnings

Mantora will **warn** (but allow) mostly read-only queries that might have performance or cost implications:

*   **No LIMIT:** `SELECT` queries without a `LIMIT` clause.
*   **SELECT *:** Fetching all columns.
*   **High Row Count:** Result sets approaching the `preview_rows` cap.

## Configuration

You can fine-tune the policy in `config.toml`:

```toml
[policy]
protective_mode = true

# specific overrides
block_ddl = true
block_dml = true
block_multi_statement = true
block_delete_without_where = true
```

### Disabling Protective Mode

To allow everything (e.g., for a "God Mode" admin agent), set `protective_mode = false`. Mantora will still log all queries but will not block anything.

## Approval Workflow

When an action is blocked or an unknown tool is used:

1.  The MCP client (Claude/Cursor) receives a "Tool Approval Required" error (or a similar message prompting the user).
2.  In the Mantora UI, the blocked action appears in the timeline.
3.  A human can click **"Allow Once"** or **"Allow Always"** (future feature) to proceed.
4.  The agent can then retry the tool call.

*(Note: "Allow" logic is currently being refined in the UI)*
