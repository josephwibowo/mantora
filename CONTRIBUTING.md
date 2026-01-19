# Contributing to Mantora

## Commit Conventions

We use **Conventional Commits** so the history stays readable and releases can be automated.

### Format

```
<type>(<scope>): <short imperative summary>
```

* **type**: what kind of change this is (required)
* **scope**: the area of the codebase (optional but recommended)
* **summary**: short, imperative, <= 72 chars

Examples:

* `feat(ui): add 3-panel layout`
* `fix(policy): block delete without where`
* `docs(readme): add 5-minute quickstart`
* `chore(build): configure ruff and mypy`

### Types

Use one of:

* **feat**: a new user-visible feature
* **fix**: a bug fix
* **docs**: documentation only
* **test**: tests only
* **refactor**: code change that doesn’t change behavior
* **perf**: performance improvement
* **chore**: tooling, build, CI, deps, repo maintenance

### Scopes

Common scopes in this repo:

* `ui` — frontend UI
* `api` — FastAPI routes / HTTP layer
* `mcp` — MCP proxy/server integration
* `policy` — protective mode, approvals, guards
* `store` — persistence (sqlite/memory), retention
* `demo` — demo data/scripts
* `build` — packaging, hatch/uv, CI
* `docs` — docs besides README
* `release` — versioning, changelog, tags

Examples:

* `feat(mcp): stream step events to UI`
* `fix(store): avoid session bleed across connections`
* `chore(release): v0.1.0`

### Commit Size / Hygiene

* Prefer **small, focused commits** (one concept per commit).
* Avoid “WIP” commits on `main`. If your branch is messy, squash/reword before merging.
* Keep generated/build artifacts out of commits unless explicitly required.

### Breaking Changes

If you introduce a breaking change, mark it explicitly:

* Use `!` in the type:
  `feat(mcp)!: change session export format`
* And/or add a footer:

  ```
  BREAKING CHANGE: explain what changed and how to migrate.
  ```

### Optional: Issue References

If relevant, reference issues in the footer:

```
Refs: #123
Fixes: #456
```

---

## Quick Demo (Docker)
Run the complete local testing environment with mock data:

```bash
docker compose up --build
```

Then open http://localhost:8000 and generate dummy sessions:

```bash
docker compose exec mantora-app uv run python scripts/setup_dummy_data.py
```

This starts:
- Mantora UI and backend (port 8000)
- Mock DuckDB server (sample query data)
- Mock Postgres server (sample schema data)

**For a deterministic demo with Cursor**: See [docs/cursor_setup.md](docs/cursor_setup.md) for a locked-down playbook that produces the same results every time.

## Repo layout
- `backend/` — Python 3.12+ FastAPI service (uses `uv`)
- `frontend/` — React + TypeScript UI (Vite, MUI, TanStack Query)

## Installation (from this repo)

To install the CLI from this repository (builds the frontend first, then installs the backend):

```bash
make install
```

## Development
### Backend
From `backend/`:
- `uv sync`
- `uv run uvicorn mantora.app:app --reload --port 8000`

The backend exposes REST + SSE under `/api`.

### Frontend
From `frontend/`:
- `pnpm install`
- `pnpm dev`

The Vite dev server runs on `http://localhost:5173` and proxies `/api` to `http://localhost:8000`.

## Production-ish local run (single server)
Build the frontend, then run the backend:

From `frontend/`:
- `pnpm install`
- `pnpm build`

From `backend/`:
- `uv sync`
- `uv run uvicorn mantora.app:app --port 8000`

When `frontend/dist` exists, the backend serves it from `/`.

## Testing

Mantora uses `pytest` for backend tests and `vitest` for frontend tests.

### Running Backend Tests
```bash
make test-be
# or
cd backend && uv run pytest
```

### Running Frontend Tests
```bash
make test-fe
# or
cd frontend && npx vitest run
```

### Linting & Formatting
Use the Makefile to ensure your code meets the project standards:
```bash
make lint-be   # Backend lint (ruff, mypy)
make format-be # Backend format
make lint-fe   # Frontend lint
make format-fe # Frontend format
```
