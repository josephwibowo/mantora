"""Tests for cast MCP tools."""

import pytest

from mantora.mcp.tools import CastTools, SessionTools
from mantora.store.memory import MemorySessionStore


@pytest.fixture
def store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
def session_tools(store: MemorySessionStore) -> SessionTools:
    return SessionTools(store)


@pytest.fixture
def cast_tools(store: MemorySessionStore, session_tools: SessionTools) -> CastTools:
    return CastTools(store, session_tools)


class TestCastTable:
    """Tests for cast_table tool."""

    def test_creates_table_cast(
        self, store: MemorySessionStore, cast_tools: CastTools, session_tools: SessionTools
    ) -> None:
        """cast_table creates a table cast artifact."""
        session_tools.session_start("test")
        session_id = session_tools.current_session_id
        assert session_id is not None

        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = cast_tools.cast_table("Test Table", "SELECT * FROM t", rows)

        assert "cast_id" in result
        assert result["rows_shown"] == 2
        assert result["total_rows"] == 2
        assert result["truncated"] is False

        # Verify stored
        casts = store.list_casts(session_id)
        assert len(casts) == 1
        assert casts[0].title == "Test Table"

    def test_truncates_large_data(self, cast_tools: CastTools, session_tools: SessionTools) -> None:
        """cast_table truncates data exceeding caps."""
        session_tools.session_start("test")

        # Create more rows than the cap (default 200)
        rows = [{"col": i} for i in range(300)]
        result = cast_tools.cast_table("Big Table", "SELECT * FROM t", rows)

        assert result["rows_shown"] == 200
        assert result["total_rows"] == 300
        assert result["truncated"] is True

    def test_auto_creates_session(self, store: MemorySessionStore, cast_tools: CastTools) -> None:
        """cast_table auto-creates session if none exists."""
        result = cast_tools.cast_table("Auto Table", "SELECT 1", [{"x": 1}])
        assert "cast_id" in result

        sessions = store.list_sessions()
        assert len(sessions) == 1


class TestEvidenceLinkage:
    """Tests for evidence linkage (PRI-EVIDENCE-LINKED)."""

    def test_cast_links_to_origin_step(
        self, store: MemorySessionStore, cast_tools: CastTools, session_tools: SessionTools
    ) -> None:
        """Casts link to their origin step ID."""
        session_tools.session_start("test")
        session_id = session_tools.current_session_id
        assert session_id is not None

        origin_id = "12345678-1234-1234-1234-123456789abc"
        cast_tools.cast_table("Test", "SELECT 1", [{"x": 1}], origin_step_id=origin_id)

        casts = store.list_casts(session_id)
        assert str(casts[0].origin_step_id) == origin_id
