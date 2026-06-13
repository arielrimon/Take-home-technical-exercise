"""Tests for ``CsvReportFormatter`` (header + one row per category)."""

from __future__ import annotations

from logstats.models import CategoryShare, DimensionStatistics, StatisticalReport
from logstats.reporting import CsvReportFormatter


def test_csv_format_has_header_and_rows(sample_report) -> None:
    rendered = CsvReportFormatter().format(sample_report)
    lines = rendered.splitlines()
    assert lines[0] == "dimension,value,count,percentage"
    assert "Country,United States,70,70.00" in lines
    assert "OS,Windows,100,100.00" in lines


def test_csv_defuses_formula_injection_in_values() -> None:
    # A category value lifted from an attacker-controlled field could start with
    # a spreadsheet formula trigger (``=``/``+``/``-``/``@``). It must be prefixed
    # with a single quote so the spreadsheet treats it as literal text on open.
    report = StatisticalReport(
        source="s",
        total_lines=1,
        parsed_records=1,
        skipped_lines=0,
        dimensions=[
            DimensionStatistics(
                name="Path",
                total=1,
                shares=[CategoryShare(value="=cmd|'/c calc'!A1", count=1, percentage=100.0)],
            )
        ],
    )
    rendered = CsvReportFormatter().format(report)
    [data_row] = [line for line in rendered.splitlines() if "cmd" in line]
    # The dangerous leading "=" is neutralised with a leading single quote.
    assert ",'=cmd" in data_row
