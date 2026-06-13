"""The formatter registry — maps a ``--format`` name to its formatter.

Adding a format is a one-line registration here plus the formatter class in a
sibling module.
"""

from __future__ import annotations

from logstats.reporting.base import ReportFormatter
from logstats.reporting.console import ConsoleReportFormatter
from logstats.reporting.csv_report import CsvReportFormatter
from logstats.reporting.json_report import JsonReportFormatter
from logstats.reporting.text import TextReportFormatter

FORMATTER_REGISTRY: dict[str, type[ReportFormatter]] = {
    "text": TextReportFormatter,
    "console": ConsoleReportFormatter,
    "json": JsonReportFormatter,
    "csv": CsvReportFormatter,
}

DEFAULT_FORMAT = "text"


def build_formatter(
    format_name: str,
    *,
    color: bool = True,
    width: int | None = None,
) -> ReportFormatter:
    """Instantiate the formatter registered under ``format_name``.

    ``color`` / ``width`` are forwarded to the colour-aware console formatter and
    ignored by the stateless ones. Raises ``KeyError`` (carrying the bad name)
    for an unknown format so the CLI can present the list of supported formats.
    """
    try:
        formatter_class = FORMATTER_REGISTRY[format_name]
    except KeyError:
        raise KeyError(format_name) from None
    if formatter_class is ConsoleReportFormatter:
        return ConsoleReportFormatter(color=color, width=width)
    return formatter_class()
