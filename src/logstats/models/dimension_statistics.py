"""The :class:`DimensionStatistics` model — one dimension's full breakdown."""

from __future__ import annotations

from pydantic import BaseModel

from logstats.models.category_share import CategoryShare


class DimensionStatistics(BaseModel):
    """The full frequency breakdown for one dimension, sorted by share.

    ``shares`` is ordered by ``count`` descending (with an alphabetical tie
    break) so the report is deterministic and directly renderable.
    """

    name: str
    """Human-readable dimension name shown in the report (e.g. ``Country``)."""

    total: int
    """Number of records the percentages are computed against."""

    shares: list[CategoryShare]
    """Per-category breakdown, already sorted by frequency descending."""
