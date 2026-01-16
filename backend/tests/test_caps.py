"""Tests for caps enforcement module."""

from __future__ import annotations

from mantora.policy.caps import (
    CappedResult,
    CapsConfig,
    cap_preview,
    cap_tabular_data,
    cap_text_preview,
)


class TestCapTextPreview:
    """Tests for text preview capping."""

    def test_no_truncation_needed(self) -> None:
        """Text under limit is not truncated."""
        result = cap_text_preview("hello", max_bytes=100)
        assert result.data == "hello"
        assert not result.bytes_truncated
        assert not result.was_truncated

    def test_truncation_applied(self) -> None:
        """Text over limit is truncated."""
        text = "a" * 100
        result = cap_text_preview(text, max_bytes=50)
        assert len(result.data.encode("utf-8")) <= 50
        assert result.bytes_truncated
        assert result.was_truncated

    def test_unicode_handling(self) -> None:
        """Unicode text is truncated correctly at byte boundaries."""
        # Each emoji is 4 bytes in UTF-8
        text = "🎉" * 10  # 40 bytes
        result = cap_text_preview(text, max_bytes=20)
        assert len(result.data.encode("utf-8")) <= 20
        assert result.bytes_truncated

    def test_truncation_summary(self) -> None:
        """Truncation summary is generated correctly."""
        result = cap_text_preview("a" * 100, max_bytes=50)
        assert result.truncation_summary == "Truncated: bytes"


class TestCapTabularData:
    """Tests for tabular data capping."""

    def test_no_truncation_needed(self) -> None:
        """Data under limits is not truncated."""
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = cap_tabular_data(rows, max_rows=10, max_columns=10)
        assert result.data == rows
        assert not result.rows_truncated
        assert not result.columns_truncated
        assert not result.was_truncated

    def test_row_truncation(self) -> None:
        """Rows over limit are truncated."""
        rows = [{"id": i} for i in range(100)]
        result = cap_tabular_data(rows, max_rows=10, max_columns=10)
        assert len(result.data) == 10
        assert result.rows_truncated
        assert not result.columns_truncated
        assert result.was_truncated

    def test_column_truncation(self) -> None:
        """Columns over limit are truncated."""
        row = {f"col_{i}": i for i in range(100)}
        rows = [row]
        result = cap_tabular_data(rows, max_rows=10, max_columns=5)
        assert len(result.data[0]) == 5
        assert not result.rows_truncated
        assert result.columns_truncated
        assert result.was_truncated

    def test_both_truncations(self) -> None:
        """Both rows and columns can be truncated."""
        row = {f"col_{i}": i for i in range(100)}
        rows = [row.copy() for _ in range(100)]
        result = cap_tabular_data(rows, max_rows=5, max_columns=3)
        assert len(result.data) == 5
        assert len(result.data[0]) == 3
        assert result.rows_truncated
        assert result.columns_truncated
        assert result.truncation_summary == "Truncated: rows, columns"

    def test_empty_data(self) -> None:
        """Empty data is handled gracefully."""
        result = cap_tabular_data([], max_rows=10, max_columns=10)
        assert result.data == []
        assert not result.was_truncated


class TestCapPreview:
    """Tests for the unified cap_preview function."""

    def test_string_data(self) -> None:
        """String data is capped by bytes."""
        config = CapsConfig(max_bytes=50)
        result = cap_preview("a" * 100, config=config)
        assert len(result.data.encode("utf-8")) <= 50
        assert result.bytes_truncated

    def test_tabular_data(self) -> None:
        """Tabular data is capped by rows and columns."""
        config = CapsConfig(max_rows=5, max_columns=3)
        rows = [{f"col_{i}": i for i in range(10)} for _ in range(10)]
        result = cap_preview(rows, config=config)
        assert len(result.data) == 5
        assert len(result.data[0]) == 3

    def test_unknown_type_passthrough(self) -> None:
        """Unknown types are passed through unchanged."""
        data = 12345
        result = cap_preview(data)
        assert result.data == data
        assert not result.was_truncated

    def test_default_config(self) -> None:
        """Default config is used when none provided."""
        result = cap_preview("hello")
        assert result.data == "hello"
        assert not result.was_truncated


class TestCapsConfig:
    """Tests for CapsConfig."""

    def test_default_values(self) -> None:
        """Default values are sensible."""
        config = CapsConfig()
        assert config.max_rows == 200
        assert config.max_columns == 80
        assert config.max_bytes == 512 * 1024

    def test_custom_values(self) -> None:
        """Custom values can be set."""
        config = CapsConfig(max_rows=10, max_columns=5, max_bytes=1024)
        assert config.max_rows == 10
        assert config.max_columns == 5
        assert config.max_bytes == 1024


class TestCappedResult:
    """Tests for CappedResult dataclass."""

    def test_was_truncated_false(self) -> None:
        """was_truncated is False when nothing truncated."""
        result = CappedResult(data="test")
        assert not result.was_truncated
        assert result.truncation_summary is None

    def test_was_truncated_rows(self) -> None:
        """was_truncated is True when rows truncated."""
        result = CappedResult(data=[], rows_truncated=True)
        assert result.was_truncated
        assert result.truncation_summary == "Truncated: rows"

    def test_was_truncated_columns(self) -> None:
        """was_truncated is True when columns truncated."""
        result = CappedResult(data=[], columns_truncated=True)
        assert result.was_truncated
        assert result.truncation_summary == "Truncated: columns"

    def test_was_truncated_bytes(self) -> None:
        """was_truncated is True when bytes truncated."""
        result = CappedResult(data="", bytes_truncated=True)
        assert result.was_truncated
        assert result.truncation_summary == "Truncated: bytes"

    def test_multiple_truncations(self) -> None:
        """Multiple truncation types are reported."""
        result = CappedResult(
            data=[], rows_truncated=True, columns_truncated=True, bytes_truncated=True
        )
        assert result.was_truncated
        assert result.truncation_summary == "Truncated: rows, columns, bytes"
