"""Tests for ``TextReportFormatter`` (plain two-decimal percentage layout)."""

from __future__ import annotations

from logstats.models import CategoryShare, DimensionStatistics, StatisticalReport
from logstats.reporting import TextReportFormatter


def test_text_format_matches_sample_layout(sample_report) -> None:
    rendered = TextReportFormatter().format(sample_report)
    assert rendered == (
        "Country:\n"
        "United States 70.00%\n"
        "France 30.00%\n"
        "\n"
        "\n"
        "\n"
        "OS:\n"
        "Windows 100.00%"
    )


def test_text_format_uses_two_decimals() -> None:
    report = StatisticalReport(
        source="s",
        total_lines=3,
        parsed_records=3,
        skipped_lines=0,
        dimensions=[
            DimensionStatistics(
                name="OS",
                total=3,
                shares=[CategoryShare(value="Windows", count=1, percentage=100 / 3)],
            )
        ],
    )
    assert "Windows 33.33%" in TextReportFormatter().format(report)
