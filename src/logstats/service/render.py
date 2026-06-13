"""Convenience for the "report → string" step in any registered format."""

from __future__ import annotations

from logstats.models import StatisticalReport
from logstats.reporting import DEFAULT_FORMAT, ReportFormatter, build_formatter


def render_report(
    report: StatisticalReport,
    format_name: str = DEFAULT_FORMAT,
    *,
    color: bool = True,
    width: int | None = None,
) -> str:
    """Render a report to a string in any registered format (text/console/json/csv).

    Thin convenience over :func:`logstats.reporting.build_formatter` so a caller
    can do the whole "data → string" step with a single import from the service.
    """
    formatter: ReportFormatter = build_formatter(format_name, color=color, width=width)
    return formatter.format(report)
