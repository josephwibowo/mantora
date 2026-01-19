# Golden Traces (Synthetic + Recorded)

Mantora’s connector tests can run against **golden traces**: captured MCP tool schemas and tool call responses that are replayed deterministically in tests.

This repo currently supports two modes:

1. **Synthetic fixtures (scaffolding)**: hand-authored JSON fixtures that exercise adapter normalization and replay infrastructure without requiring cloud accounts.
2. **Recorded fixtures (recommended)**: captured from real MCP servers/accounts, sanitized before committing.

## Layout

- `backend/tests/golden/schema.json`: JSON Schema for fixture files
- `backend/tests/golden/<target>/tools.json`: tool definitions from `list_tools`
- `backend/tests/golden/<target>/traces/*.json`: request/response traces
- `backend/tests/fixtures/mock_<target>_server.py`: stdio MCP servers that replay fixtures

## Running tests

From `backend/`:

- `uv run pytest -k golden_traces`

## Recording real traces

The recorder writes files under `backend/tests/golden/<target>/` and sanitizes common sensitive values (tokens/emails/project IDs/timestamps/UUIDs).

From `backend/`:

- `uv run python scripts/record_mcp_trace.py --target-type bigquery --command <your-mcp-server-cmd...> --playbook <playbook.json>`

### Playbook format

`--playbook` is a JSON (or YAML if you have PyYAML installed) list of tool calls:

```json
[
  { "id": "list_datasets", "tool_name": "list_dataset_ids", "arguments": { "project_id": "my-project" } },
  { "id": "query_select", "tool_name": "execute_sql", "arguments": { "sql": "SELECT 1" } }
]
```

Notes:
- Prefer stable, low-cost calls (metadata + tiny SELECTs).
- Keep arguments deterministic; anything environment-specific should be sanitized.

## Updating fixtures

When upstream MCP servers change:

1. Re-record with `record_mcp_trace.py`
2. Review diffs for accidental sensitive values
3. Run `uv run pytest -k golden_traces` to ensure adapters still normalize as expected

