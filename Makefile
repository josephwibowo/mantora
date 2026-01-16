.PHONY: install up down run-proxy
.SILENT:

# Default connector extras to install into the pipx venv.
# Override: `make install MANTORA_EXTRAS=all` or `MANTORA_EXTRAS=postgres`.
MANTORA_EXTRAS ?= duckdb

install:
	@echo "Building frontend..."
	@corepack enable
	@cd frontend && pnpm install && pnpm build
	@echo "Installing backend CLI..."
	-pipx uninstall mantora
	@MANTORA_ENFORCE_FRONTEND_DIST=1 pipx install "./backend[$(MANTORA_EXTRAS)]" --force

up:
	docker compose up -d --build

down:
	docker compose down

run-proxy:
	@PYTHONPATH=backend/src uv run --project backend python -m mantora.cli mcp --config mantora.toml

lint-fe:
	@echo "Linting frontend..."
	@cd frontend && pnpm run typecheck
	@cd frontend && pnpm run lint
	@cd frontend && pnpm run format:check

format-fe:
	@echo "Formatting frontend..."
	@cd frontend && pnpm run format:write
	@cd frontend && pnpm run lint --fix

test-fe:
	@echo "Testing frontend..."
	@cd frontend && npx vitest run

lint-be:
	@echo "Linting backend..."
	@cd backend && uv run ruff check
	@cd backend && uv run mypy .

format-be:
	@echo "Formatting backend..."
	@cd backend && uv run ruff check --fix
	@cd backend && uv run ruff format

test-be:
	@echo "Testing backend..."
	@cd backend && uv run pytest
