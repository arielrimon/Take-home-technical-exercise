"""JSON formatter — machine-readable output including parse-quality metadata."""

from __future__ import annotations

import json

from logstats.models import StatisticalReport
from logstats.reporting.base import PERCENT_DECIMALS


class JsonReportFormatter:
    """Renders the report as indented JSON including parse-quality metadata.

    Useful for downstream tooling: it exposes raw counts alongside the rounded
    percentages and reports how many lines were read / parsed / skipped.
    """

    def format(self, report: StatisticalReport) -> str:
        """Serialise the full report (metadata + per-dimension breakdowns) to JSON."""
        payload = {
            "source": report.source,
            "total_lines": report.total_lines,
            "parsed_records": report.parsed_records,
            "skipped_lines": report.skipped_lines,
            "dimensions": [
                {
                    "name": dimension.name,
                    "total": dimension.total,
                    "shares": [
                        {
                            "value": share.value,
                            "count": share.count,
                            "percentage": round(share.percentage, PERCENT_DECIMALS),
                        }
                        for share in dimension.shares
                    ],
                }
                for dimension in report.dimensions
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)
