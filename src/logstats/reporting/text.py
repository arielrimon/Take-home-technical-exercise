"""Plain-text formatter — the layout matching the assignment's sample output."""

from __future__ import annotations

from logstats.models import StatisticalReport
from logstats.reporting.base import PERCENT_DECIMALS


class TextReportFormatter:
    """Renders the report as plain text, one block per dimension.

    Each block is the dimension name followed by ``"<value> <pct>%"`` lines,
    sorted by frequency descending, with percentages fixed to two decimals —
    exactly the layout shown in the assignment's "Sample Output Format".
    """

    def format(self, report: StatisticalReport) -> str:
        """Build the multi-block text report and return it as one string."""
        blocks: list[str] = []
        for dimension in report.dimensions:
            lines = [f"{dimension.name}:"]
            lines.extend(
                f"{share.value} {share.percentage:.{PERCENT_DECIMALS}f}%"
                for share in dimension.shares
            )
            blocks.append("\n".join(lines))
        # Three blank lines between dimension blocks give each metric strong
        # visual separation in the plain-text report.
        return "\n\n\n\n".join(blocks)
