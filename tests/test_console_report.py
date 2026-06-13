"""Tests for ``ConsoleReportFormatter`` (coloured/monochrome bar-chart output)."""

from __future__ import annotations

from logstats.models import CategoryShare, DimensionStatistics, StatisticalReport
from logstats.reporting import ConsoleReportFormatter


def test_console_format_monochrome_has_data_and_no_ansi(sample_report) -> None:
    rendered = ConsoleReportFormatter(color=False, width=80).format(sample_report)
    # Content is present (dimension names, categories, two-decimal percentages).
    assert "Country" in rendered
    assert "United States" in rendered
    assert "70.00%" in rendered
    # With colour disabled there must be no ANSI escape sequences.
    assert "\x1b" not in rendered
    # The inline bar chart is rendered with block characters.
    assert "█" in rendered


def test_console_format_color_emits_ansi(sample_report) -> None:
    rendered = ConsoleReportFormatter(color=True, width=80).format(sample_report)
    assert "\x1b" in rendered  # ANSI styling present when colour is on
    assert "United States" in rendered


def test_console_format_escapes_markup_in_category_values() -> None:
    # Category values can be attacker-controlled (e.g. a request path for an
    # extension dimension). A value containing Rich-markup syntax must be treated
    # as literal text: an unmatched closing tag like ``[/]`` would otherwise raise
    # MarkupError and abort the whole render, and ``[bold]`` would silently style.
    report = StatisticalReport(
        source="[/]injected-source",
        total_lines=1,
        parsed_records=1,
        skipped_lines=0,
        dimensions=[
            DimensionStatistics(
                name="Path",
                total=1,
                shares=[CategoryShare(value="[/]", count=1, percentage=100.0)],
            )
        ],
    )
    # Must not raise, and the literal bracket text must survive into the output.
    rendered = ConsoleReportFormatter(color=True, width=80).format(report)
    assert "[/]" in rendered


def test_console_format_handles_empty_dimension() -> None:
    empty = StatisticalReport(
        source="s",
        total_lines=0,
        parsed_records=0,
        skipped_lines=0,
        dimensions=[DimensionStatistics(name="Country", total=0, shares=[])],
    )
    rendered = ConsoleReportFormatter(color=False, width=80).format(empty)
    assert "no data" in rendered
