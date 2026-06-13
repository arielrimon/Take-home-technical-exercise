"""Tests for the formatter registry and ``build_formatter`` factory."""

from __future__ import annotations

from logstats.reporting import (
    ConsoleReportFormatter,
    CsvReportFormatter,
    JsonReportFormatter,
    TextReportFormatter,
    build_formatter,
)


def test_build_formatter_returns_requested_type() -> None:
    assert isinstance(build_formatter("text"), TextReportFormatter)
    assert isinstance(build_formatter("console"), ConsoleReportFormatter)
    assert isinstance(build_formatter("json"), JsonReportFormatter)
    assert isinstance(build_formatter("csv"), CsvReportFormatter)
