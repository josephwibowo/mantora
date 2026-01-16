# Mantora

Mantora is a local-first MCP observer: a lightweight UI + proxy for inspecting LLM data access (sessions, tool calls, results) with protective defaults.

## Install

```bash
pipx install "mantora[duckdb]"
# or
uv tool install "mantora[duckdb]"
```

Extras:
- `mantora[duckdb]` installs DuckDB connector dependencies
- `mantora[postgres]` installs Postgres connector dependencies
- `mantora[all]` installs both

## Usage

```bash
mantora up
mantora --help
mantora --version
```

Repository: https://github.com/josephwibowo/mantora-mcp
