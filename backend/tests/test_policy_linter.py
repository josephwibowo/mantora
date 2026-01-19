from __future__ import annotations

from unittest.mock import patch

from mantora.policy.linter import extract_tables_touched, lint_sql
from mantora.policy.sql_guard import SQLWarning


def test_lint_sql_detects_select_star() -> None:
    # SQLGlot should find this
    warnings = lint_sql("SELECT * FROM users")
    assert SQLWarning.SELECT_STAR in warnings


def test_lint_sql_detects_no_limit() -> None:
    warnings = lint_sql("SELECT * FROM users")
    # Should catch both
    assert SQLWarning.NO_LIMIT in warnings
    assert SQLWarning.SELECT_STAR in warnings

    # With limit, should be fine
    warnings_ok = lint_sql("SELECT * FROM users LIMIT 10")
    assert SQLWarning.NO_LIMIT not in warnings_ok


def test_lint_sql_detects_delete_no_where() -> None:
    warnings = lint_sql("DELETE FROM users")
    assert SQLWarning.DELETE_NO_WHERE in warnings

    warnings_ok = lint_sql("DELETE FROM users WHERE id = 1")
    assert SQLWarning.DELETE_NO_WHERE not in warnings_ok


def test_lint_sql_detects_multi_statement() -> None:
    warnings = lint_sql("SELECT 1; SELECT 2")
    assert SQLWarning.MULTI_STATEMENT in warnings


def test_extract_tables_complex_sql() -> None:
    sql = """
    WITH cte AS (SELECT * FROM raw_data)
    SELECT * 
    FROM clean_data 
    JOIN analytics.users ON clean_data.id = users.id
    WHERE exists (select 1 from metadata)
    """
    tables = extract_tables_touched(sql)
    assert tables is not None
    # ordering is sorted
    assert "analytics.users" in tables
    assert "clean_data" in tables
    # "raw_data" and "metadata" should also be found by sqlglot
    assert "raw_data" in tables
    assert "metadata" in tables


def test_lint_fallback_regex() -> None:
    # Simulate missing sqlglot by mocking the import inside linter
    with patch("mantora.policy.linter._lint_sqlglot", return_value=None):
        warnings = lint_sql("SELECT * FROM users")
        # Regex should still catch SELECT *
        assert SQLWarning.SELECT_STAR in warnings

        warnings_del = lint_sql("DELETE FROM users")
        assert SQLWarning.DELETE_NO_WHERE in warnings_del


def test_count_star_not_flagged() -> None:
    """COUNT(*) should NOT trigger SELECT_STAR warning."""
    warnings = lint_sql("SELECT COUNT(*) FROM users")
    assert SQLWarning.SELECT_STAR not in warnings
    # But it should still warn about NO_LIMIT
    assert SQLWarning.NO_LIMIT in warnings


def test_cte_with_select_star() -> None:
    """SELECT * inside a CTE should be detected."""
    sql = "WITH cte AS (SELECT * FROM raw_data) SELECT id FROM cte"
    warnings = lint_sql(sql)
    assert SQLWarning.SELECT_STAR in warnings


def test_select_with_where_no_limit_warning() -> None:
    """SELECT with WHERE but no LIMIT should not warn (heuristic)."""
    warnings = lint_sql("SELECT * FROM users WHERE active = true")
    # Should have SELECT_STAR but not NO_LIMIT (WHERE clause present)
    assert SQLWarning.SELECT_STAR in warnings
    assert SQLWarning.NO_LIMIT not in warnings


def test_insert_select_star() -> None:
    """INSERT ... SELECT * should detect SELECT_STAR and DML."""
    sql = "INSERT INTO archive SELECT * FROM users"
    warnings = lint_sql(sql)
    assert SQLWarning.SELECT_STAR in warnings
    assert SQLWarning.DML in warnings


def test_ddl_detection() -> None:
    """DDL statements should be tagged."""
    warnings_create = lint_sql("CREATE TABLE users (id INT)")
    assert SQLWarning.DDL in warnings_create

    warnings_drop = lint_sql("DROP TABLE users")
    assert SQLWarning.DDL in warnings_drop

    warnings_alter = lint_sql("ALTER TABLE users ADD COLUMN name VARCHAR(100)")
    assert SQLWarning.DDL in warnings_alter


def test_complex_multi_table_query() -> None:
    """Complex query with multiple tables should extract all."""
    sql = """
    SELECT u.id, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    LEFT JOIN payments p ON o.id = p.order_id
    WHERE u.active = true
    """
    tables = extract_tables_touched(sql)
    assert tables is not None
    assert "users" in tables
    assert "orders" in tables
    assert "payments" in tables
