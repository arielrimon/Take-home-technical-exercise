"""The :class:`StatisticalReport` model — the full multi-dimension result."""

from __future__ import annotations

from pydantic import BaseModel

from logstats.models.dimension_statistics import DimensionStatistics


class StatisticalReport(BaseModel):
    """The complete result of analysing a log file across every dimension.

    Besides the per-dimension breakdowns it carries provenance/quality metadata
    (how many lines were read, parsed, and skipped) so a consumer can judge how
    trustworthy the percentages are.
    """

    source: str
    """Identifier of the analysed input (file path or ``<stdin>``)."""

    total_lines: int
    """Total non-empty lines read from the source."""

    parsed_records: int
    """Lines that parsed successfully and contributed to the statistics."""

    skipped_lines: int
    """Lines that failed to parse and were excluded (e.g. truncated entries)."""

    dimensions: list[DimensionStatistics]
    """One breakdown per analysed dimension, in the order they were requested."""
