"""The :class:`PartialAggregate` model — one worker's slice of the work.

In the parallel path each worker process aggregates its own shard of the file
and returns a :class:`PartialAggregate`: the raw per-dimension category counts
plus the line accounting and stage timings for that shard. The orchestrator sums
these partials (counters merge by addition, which is associative and
order-independent) into the final :class:`StatisticalReport`.

It carries plain ``dict`` counts rather than :class:`collections.Counter` or live
``Dimension`` objects precisely because it must cross a process boundary: the
resolvers a dimension holds (an open GeoIP database handle, the UA parser) are
not picklable, but a ``{dimension_name: {category: count}}`` map is.
"""

from __future__ import annotations

from pydantic import BaseModel

from logstats.models.stage_timings import StageTimings


class PartialAggregate(BaseModel):
    """The picklable result of aggregating one shard of the input.

    ``dimension_names`` preserves the requested dimension order so the
    orchestrator can assemble the final report deterministically without
    rebuilding the (resolver-backed) dimension objects itself.
    """

    dimension_names: list[str]
    """Dimension names, in requested order (same across every shard)."""

    dimension_to_counts: dict[str, dict[str, int]]
    """Per dimension, a ``{category: count}`` tally for this shard."""

    record_count: int
    """Records that parsed successfully and were counted in this shard."""

    total_lines: int
    """Non-empty lines read from this shard."""

    skipped_lines: int
    """Lines in this shard that failed to parse and were skipped."""

    timings: StageTimings
    """Where this shard's wall-clock time went (read / parse / aggregate)."""
