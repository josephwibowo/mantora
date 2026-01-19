"""Tests for SQL guard module."""

from __future__ import annotations

import pytest

from mantora.config.settings import PolicyConfig
from mantora.policy.sql_guard import (
    SQLClassification,
    SQLWarning,
    analyze_sql,
    should_block_sql,
)


class TestSQLClassification:
    """Tests for SQL classification."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM users",
            "select id, name from products",
            "SELECT COUNT(*) FROM orders WHERE status = 'active'",
            "WITH cte AS (SELECT * FROM t) SELECT * FROM cte",
            "EXPLAIN SELECT * FROM users",
            "SHOW TABLES",
            "DESCRIBE users",
            "PRAGMA table_info(users)",
        ],
    )
    def test_read_only_classification(self, sql: str) -> None:
        """Read-only SQL is classified correctly."""
        result = analyze_sql(sql)
        assert result.classification == SQLClassification.read_only
        assert result.is_safe

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO users (name) VALUES ('test')",
            "UPDATE users SET name = 'new' WHERE id = 1",
            "DELETE FROM users WHERE id = 1",
            "DROP TABLE users",
            "CREATE TABLE new_table (id INT)",
            "ALTER TABLE users ADD COLUMN email TEXT",
            "TRUNCATE TABLE users",
            "MERGE INTO target USING source ON ...",
            "GRANT SELECT ON users TO role",
            "REVOKE SELECT ON users FROM role",
            "COPY users FROM '/path/to/file'",
            "EXECUTE stored_proc()",
            "CALL my_procedure()",
        ],
    )
    def test_destructive_classification(self, sql: str) -> None:
        """Destructive SQL is classified correctly."""
        result = analyze_sql(sql)
        assert result.classification == SQLClassification.destructive
        assert not result.is_safe

    def test_unknown_classification(self) -> None:
        """Unknown SQL patterns are classified as unknown."""
        result = analyze_sql("SOME_VENDOR_SPECIFIC_COMMAND")
        assert result.classification == SQLClassification.unknown

    def test_empty_sql(self) -> None:
        """Empty SQL is handled gracefully."""
        result = analyze_sql("")
        assert result.classification == SQLClassification.unknown
        assert result.reason == "Empty SQL"

        result = analyze_sql("   ")
        assert result.classification == SQLClassification.unknown


class TestMultiStatementDetection:
    """Tests for multi-statement SQL detection."""

    def test_single_statement(self) -> None:
        """Single statements are not flagged."""
        result = analyze_sql("SELECT * FROM users")
        assert not result.is_multi_statement

    def test_single_statement_with_trailing_semicolon(self) -> None:
        """Trailing semicolon doesn't trigger multi-statement."""
        result = analyze_sql("SELECT * FROM users;")
        assert not result.is_multi_statement

        result = analyze_sql("SELECT * FROM users;  ")
        assert not result.is_multi_statement

    def test_multi_statement_detected(self) -> None:
        """Multiple statements are detected."""
        result = analyze_sql("SELECT 1; SELECT 2")
        assert result.is_multi_statement
        assert not result.is_safe

    def test_multi_statement_with_newlines(self) -> None:
        """Multi-statement with newlines is detected."""
        sql = """SELECT * FROM users;
        DELETE FROM users WHERE id = 1"""
        result = analyze_sql(sql)
        assert result.is_multi_statement


class TestShouldBlockSQL:
    """Tests for should_block_sql function."""

    def test_protective_mode_blocks_destructive(self) -> None:
        """Protective mode blocks destructive SQL."""
        policy = PolicyConfig(protective_mode=True)
        should_block, reason = should_block_sql("DELETE FROM users", policy=policy)
        assert should_block
        assert reason is not None
        # v0: return a specific detection reason (more actionable than a generic message)
        assert "delete" in reason.lower()

    def test_protective_mode_blocks_multi_statement(self) -> None:
        """Protective mode blocks multi-statement SQL."""
        policy = PolicyConfig(protective_mode=True)
        should_block, reason = should_block_sql("SELECT 1; SELECT 2", policy=policy)
        assert should_block
        assert reason is not None
        assert "multi-statement" in reason.lower()

    def test_protective_mode_allows_read_only(self) -> None:
        """Protective mode allows read-only SQL."""
        policy = PolicyConfig(protective_mode=True)
        should_block, reason = should_block_sql("SELECT * FROM users", policy=policy)
        assert not should_block
        assert reason is None

    def test_transparent_mode_allows_all(self) -> None:
        """Transparent mode allows all SQL."""
        policy = PolicyConfig(protective_mode=False)
        # Destructive
        should_block, _ = should_block_sql("DELETE FROM users", policy=policy)
        assert not should_block

        # Multi-statement
        should_block, _ = should_block_sql("SELECT 1; SELECT 2", policy=policy)
        assert not should_block

    def test_protective_mode_allows_unknown(self) -> None:
        """Protective mode allows unknown SQL (for usability)."""
        policy = PolicyConfig(protective_mode=True)
        should_block, reason = should_block_sql("SOME_UNKNOWN_COMMAND", policy=policy)
        assert not should_block
        assert reason is None


class TestEdgeCases:
    """Tests for edge cases and potential false positives."""

    def test_keyword_in_string_literal(self) -> None:
        """Keywords in string literals may cause false positives (known limitation)."""
        # This is a known limitation of v0 heuristics
        # The word DELETE appears in the string, triggering detection
        sql = "SELECT * FROM logs WHERE message LIKE '%DELETE%'"
        result = analyze_sql(sql)
        # This will be classified as destructive due to keyword presence
        # Future versions with proper parsing will handle this correctly
        assert result.classification == SQLClassification.destructive

    def test_case_insensitivity(self) -> None:
        """Classification is case-insensitive."""
        result = analyze_sql("delete from users")
        assert result.classification == SQLClassification.destructive

        result = analyze_sql("DeLeTe FrOm UsErS")
        assert result.classification == SQLClassification.destructive

    def test_whitespace_handling(self) -> None:
        """Whitespace is handled correctly."""
        result = analyze_sql("  SELECT * FROM users  ")
        assert result.classification == SQLClassification.read_only

        result = analyze_sql("\n\tSELECT * FROM users\n")
        assert result.classification == SQLClassification.read_only


class TestWarnings:
    def test_no_limit_warning_suppressed_with_where_clause(self) -> None:
        result = analyze_sql("SELECT * FROM orders WHERE created_at > '2025-12-29'")
        assert SQLWarning.SELECT_STAR in result.warnings
        assert SQLWarning.NO_LIMIT not in result.warnings

    def test_no_limit_warning_emitted_without_where_clause(self) -> None:
        result = analyze_sql("SELECT * FROM orders")
        assert SQLWarning.SELECT_STAR in result.warnings
        assert SQLWarning.NO_LIMIT in result.warnings
