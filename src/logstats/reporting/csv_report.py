"""CSV formatter — flat ``dimension,value,count,percentage`` rows."""

from __future__ import annotations

import csv
import io

from logstats.models import StatisticalReport
from logstats.reporting.base import PERCENT_DECIMALS

# Leading characters a spreadsheet (Excel / Google Sheets / LibreOffice) treats
# as the start of a formula. A category value such as ``=cmd|...`` lifted from an
# attacker-controlled request field would otherwise be executed on open, so any
# value beginning with one of these is defused by prefixing a single quote — the
# standard CSV-injection mitigation. ``\t`` / ``\r`` are included because some
# importers strip leading whitespace and then re-evaluate the first real char.
_FORMULA_TRIGGER_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class CsvReportFormatter:
    """Renders the report as flat CSV rows: ``dimension,value,count,percentage``.

    One row per category across all dimensions, which is convenient for loading
    into a spreadsheet or a dataframe for further analysis.
    """

    _HEADER = ("dimension", "value", "count", "percentage")

    def format(self, report: StatisticalReport) -> str:
        """Serialise every category of every dimension as one CSV row each."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(self._HEADER)
        for dimension in report.dimensions:
            for share in dimension.shares:
                writer.writerow(
                    (
                        self._defuse_formula(dimension.name),
                        self._defuse_formula(share.value),
                        share.count,
                        f"{share.percentage:.{PERCENT_DECIMALS}f}",
                    )
                )
        return buffer.getvalue().strip("\r\n")

    @staticmethod
    def _defuse_formula(value: str) -> str:
        """Neutralise CSV/spreadsheet formula injection in a free-text field.

        Prefixes a single quote when ``value`` starts with a formula-trigger
        character so the spreadsheet treats the cell as literal text instead of
        evaluating it. Returns the value untouched when it is safe.
        """
        if value.startswith(_FORMULA_TRIGGER_PREFIXES):
            return f"'{value}"
        return value
