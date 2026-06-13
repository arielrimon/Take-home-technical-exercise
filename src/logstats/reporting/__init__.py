"""Reporting package — render a :class:`StatisticalReport` into a chosen format.

Adding a new output format is just adding a formatter module and one line in the
registry; the analysis pipeline never changes.

Layout (one formatter per module):

* :mod:`logstats.reporting.base`        — the ``ReportFormatter`` protocol
* :mod:`logstats.reporting.text`        — ``TextReportFormatter`` (the assignment's sample layout)
* :mod:`logstats.reporting.console`     — ``ConsoleReportFormatter`` (coloured tables + bar charts)
* :mod:`logstats.reporting.json_report` — ``JsonReportFormatter``
* :mod:`logstats.reporting.csv_report`  — ``CsvReportFormatter``
* :mod:`logstats.reporting.registry`    — name → formatter registry + ``build_formatter``
"""

from logstats.reporting.base import ReportFormatter
from logstats.reporting.console import ConsoleReportFormatter
from logstats.reporting.csv_report import CsvReportFormatter
from logstats.reporting.json_report import JsonReportFormatter
from logstats.reporting.registry import DEFAULT_FORMAT, FORMATTER_REGISTRY, build_formatter
from logstats.reporting.text import TextReportFormatter

__all__ = [
    "DEFAULT_FORMAT",
    "FORMATTER_REGISTRY",
    "ConsoleReportFormatter",
    "CsvReportFormatter",
    "JsonReportFormatter",
    "ReportFormatter",
    "TextReportFormatter",
    "build_formatter",
]
