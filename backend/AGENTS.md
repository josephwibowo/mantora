# Backend Coding Standards

## Core Stack
**Python 3.12+ • FastAPI • Pydantic • uv • SQLite (via SQLModel/SQLAlchemy)**

## Tooling & Workflow
1. **Dependency Management (`uv`)**:
   - Install: `uv sync`
   - Add packages: `uv add <package>`
   - Run commands: `uv run <command>` (e.g., `uv run python src/mantora/app.py`)
2. **Linting & Formatting (`ruff`)**:
   - Check: `uv run ruff check .`
   - Format: `uv run ruff format .`
   - **Rule**: PEP-8 is strictly enforced. Sort imports automatically.
3. **Type Checking (`mypy`)**:
   - Run: `uv run mypy .`
   - **Rule**: Strict typing. No implicit `Any`. Return types must be explicit for all functions.
4. **Testing (`pytest`)**:
   - Run: `uv run pytest`
   - **Rule**: Co-locate tests in `tests/`. Use `conftest.py` for shared fixtures.

## Code Style & Patterns
1. **Pydantic First**:
   - Use Pydantic models for all data schemas (API input/output, config).
   - Use `model_validate` or `model_dump` for serialization; avoid manual dict manipulation.
2. **Path Handling**:
   - Always use `pathlib.Path`, never `os.path.join`.
3. **Async/Await**:
   - FastAPI routes should be `async def`.
   - I/O operations (DB, HTTP) must be awaited.
   - CPU-bound tasks (rare) should run in a threadpool if blocking.

## Architecture
1. **Modularity**: Keep `routes`, `models`, and `services` (logic) separate.
2. **Error Handling**: Raise `HTTPException` for API errors. Use custom exception classes for domain logic errors.
3. **Configuration**: Use `pydantic-settings` or strictly typed config classes. strict validation on startup.

## Mantora Specifics
1. **Spectacles Alignment**: Check `.spectacles/` for domain rules (e.g., adapters, observers).
2. **Observability**: Log structured events, not just print statements.
