"""The :class:`ReportFormatter` protocol and shared formatting constants.

Rendering a report into a chosen output format is the second major extension
point of the module (after dimensions): **adding a new output format is just
adding a formatter file and registering it** — the analysis pipeline is untouched.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from logstats.models import StatisticalReport

# Percentages are reported to exactly two decimal places per the requirements.
PERCENT_DECIMALS = 2


@runtime_checkable
class ReportFormatter(Protocol):
    """Strategy that serialises a :class:`StatisticalReport` to a string."""

    def format(self, report: StatisticalReport) -> str:
        """Return the report rendered in this formatter's output format."""
        ...
