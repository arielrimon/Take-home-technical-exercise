"""The :class:`StageTimings` model — where wall-clock time goes in one pass.

The pipeline processes each line in three observable stages — **read** (pull the
next line from the source, i.e. file I/O or, in the parallel path, inter-process
hand-off), **parse** (regex → :class:`LogRecord`) and **aggregate** (resolve
dimensions via GeoIP / UA lookups and tally the counters). Knowing the split
between them is what tells us whether the work is I/O-bound or CPU/lookup-bound,
and therefore whether throwing more processes at it will actually help.
"""

from __future__ import annotations

from pydantic import BaseModel


class StageTimings(BaseModel):
    """Per-stage wall-clock breakdown of a single aggregation pass (seconds).

    ``read + parse + aggregate`` accounts for the per-line work; ``total`` is the
    end-to-end wall clock of the pass and is always ``>=`` their sum (it also
    covers loop overhead and the final report assembly).
    """

    read_seconds: float
    """Time spent pulling lines from the source (file I/O / IPC wait)."""

    parse_seconds: float
    """Time spent in the regex parser turning raw lines into ``LogRecord``s."""

    aggregate_seconds: float
    """Time spent resolving dimensions (GeoIP / UA lookups) and counting."""

    total_seconds: float
    """End-to-end wall clock for the whole pass (the denominator for shares)."""

    @classmethod
    def combine(cls, parts: list["StageTimings"], *, total_seconds: float) -> "StageTimings":
        """Sum the per-stage CPU work of several passes under one wall clock.

        Used by the parallel orchestrator to roll up the workers' timings: the
        stage figures are summed (total CPU-seconds spent reading / parsing /
        aggregating across all shards), while ``total_seconds`` is supplied
        separately as the orchestrator's own wall clock — comparing the two
        shows the parallel speed-up (summed CPU work ÷ wall clock ≈ effective
        cores used).
        """
        return cls(
            read_seconds=sum(part.read_seconds for part in parts),
            parse_seconds=sum(part.parse_seconds for part in parts),
            aggregate_seconds=sum(part.aggregate_seconds for part in parts),
            total_seconds=total_seconds,
        )

    def as_log_extra(self) -> dict[str, float]:
        """Render the timings as rounded ``extra=`` fields for a structured log."""
        return {
            "read_seconds": round(self.read_seconds, 4),
            "parse_seconds": round(self.parse_seconds, 4),
            "aggregate_seconds": round(self.aggregate_seconds, 4),
            "total_seconds": round(self.total_seconds, 4),
        }
