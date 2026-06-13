"""The :class:`DimensionAggregator` — streaming per-dimension frequency counts.

Fed one record at a time, it maintains a ``Counter`` per dimension. Memory is
``O(distinct category values)`` — independent of the number of log lines — so it
streams arbitrarily large files. Turning the raw counts into sorted,
percentage-based :class:`DimensionStatistics` (with the optional "Other"
long-tail bucket) is a separate, pure step in :meth:`results`.
"""

from __future__ import annotations

from collections import Counter

from logstats.dimensions import Dimension
from logstats.models import CategoryShare, DimensionStatistics, LogRecord, PartialAggregate

# Default label for the bucket that collapses the long tail of small categories
# when a ``top_n`` limit is applied. Distinct from the dimensions' UNKNOWN_LABEL:
# "Other" is a group of *known* categories, "Unknown" is a single *unresolved* one.
DEFAULT_OTHER_LABEL = "Other"

# A whole report (100.00%) expressed in hundredths-of-a-percent, the unit the
# percentage apportionment works in. Percentages are reported to two decimals, so
# 100.00% is 10000 hundredths; rounding each share to an integer count of these
# units and handing out the remainder by largest remainder makes a dimension's
# displayed percentages sum to exactly 100.00 instead of drifting to 99.99/100.01.
_PERCENT_HUNDREDTHS = 10_000


class DimensionAggregator:
    """Accumulates per-dimension category counts over a stream of records."""

    def __init__(self, dimensions: list[Dimension]) -> None:
        """Prepare an independent counter for each dimension to be tallied."""
        self._dimensions = dimensions
        # Names are cached separately from the dimension objects so the merge /
        # results path can run without live (resolver-backed) dimensions — see
        # ``for_merge`` below, used when assembling a report from worker shards.
        self._dimension_names = [dimension.name for dimension in dimensions]
        self._dimension_to_counts: dict[str, Counter[str]] = {
            name: Counter() for name in self._dimension_names
        }
        self._record_count = 0

    @classmethod
    def for_merge(cls, dimension_names: list[str]) -> "DimensionAggregator":
        """Create an empty aggregator that merges shards by name, not extraction.

        The parallel orchestrator uses this to fold worker :class:`PartialAggregate`
        results together: it needs the dimension *names* and counters but never
        calls :meth:`add` (the workers already did the extraction), so it does not
        need the resolver-backed :class:`Dimension` objects at all.
        """
        aggregator = cls([])
        aggregator._dimension_names = list(dimension_names)
        aggregator._dimension_to_counts = {name: Counter() for name in dimension_names}
        return aggregator

    @property
    def record_count(self) -> int:
        """Number of records aggregated so far (the percentage denominator)."""
        return self._record_count

    @property
    def dimension_count(self) -> int:
        """How many dimensions this aggregator tallies (for the run summary)."""
        return len(self._dimension_names)

    @property
    def dimension_names(self) -> list[str]:
        """The tallied dimension names, in requested order (a copy)."""
        return list(self._dimension_names)

    def add(self, record: LogRecord) -> None:
        """Tally ``record`` into every dimension's counter (one streaming step)."""
        self._record_count += 1
        for dimension in self._dimensions:
            category = dimension.extract(record)
            self._dimension_to_counts[dimension.name][category] += 1

    def snapshot(self) -> dict[str, dict[str, int]]:
        """Export the raw counts as plain, picklable ``{dimension: {cat: n}}`` dicts.

        Plain ``dict``s (not ``Counter``) so the result drops cleanly into a
        :class:`PartialAggregate` and survives the pickle round-trip back from a
        worker process.
        """
        return {name: dict(counts) for name, counts in self._dimension_to_counts.items()}

    def merge(self, partial: PartialAggregate) -> None:
        """Fold one worker shard's counts into this aggregator (associative add).

        Counter addition is commutative and associative, so merging shards in any
        order yields the same totals — which is what lets the shards be processed
        in parallel and reduced here without coordination.
        """
        self._record_count += partial.record_count
        for name, counts in partial.dimension_to_counts.items():
            # ``Counter.update`` adds the per-category counts onto the running
            # tally, creating any categories this shard saw for the first time.
            self._dimension_to_counts[name].update(counts)

    def results(
        self,
        top_n: int | None = None,
        other_label: str = DEFAULT_OTHER_LABEL,
    ) -> list[DimensionStatistics]:
        """Render the accumulated counts into sorted, percentage-based stats.

        Real categories are sorted by count descending with an alphabetical
        tie-break for fully deterministic output. When ``top_n`` is given, only
        the ``top_n`` most frequent categories are kept and the remainder are
        collapsed into a single ``other_label`` bucket. That synthetic bucket is
        appended last (the conventional placement for a residual catch-all, and
        what the assignment's sample output shows) rather than being ranked by
        its aggregate count.
        """
        statistics: list[DimensionStatistics] = []
        # Iterate over the cached names (not the dimension objects) so this works
        # identically for a streamed aggregator and one built via ``for_merge``.
        for name in self._dimension_names:
            counts = self._dimension_to_counts[name]
            ranked = self._rank(counts)
            if top_n is not None and len(ranked) > top_n:
                ranked = self._collapse_tail(ranked, top_n, other_label)
            # Note: the "Unknown" category (an unresolved value) is intentionally
            # NOT special-cased here. It is a real category and sorts by its own
            # frequency like any other — it can legitimately be the largest slice.
            statistics.append(
                DimensionStatistics(
                    name=name,
                    total=self._record_count,
                    shares=self._to_shares(ranked),
                )
            )
        return statistics

    @staticmethod
    def _rank(counts: Counter[str]) -> list[tuple[str, int]]:
        """Order ``(category, count)`` pairs by count desc, then label asc.

        The alphabetical secondary key makes the ordering of equal-count
        categories stable and reproducible across runs and platforms (which
        plain ``Counter.most_common`` does not guarantee).
        """
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    @staticmethod
    def _collapse_tail(
        ranked: list[tuple[str, int]],
        top_n: int,
        other_label: str,
    ) -> list[tuple[str, int]]:
        """Keep the ``top_n`` largest categories; fold the rest into ``other_label``.

        ``ranked`` is already sorted by frequency descending, so the kept slice
        preserves that order and the "Other" bucket is appended last as a
        residual catch-all.
        """
        kept = list(ranked[:top_n])
        other_count = sum(count for _, count in ranked[top_n:])
        kept.append((other_label, other_count))
        return kept

    @staticmethod
    def _to_shares(ranked: list[tuple[str, int]]) -> list[CategoryShare]:
        """Attach a two-decimal percentage to each ranked ``(category, count)`` pair.

        Uses the largest-remainder (Hamilton) method so the percentages sum to
        exactly 100.00 rather than drifting from independent per-row rounding:
        every share is first floored to a whole number of hundredths-of-a-percent
        (computed in exact integer arithmetic to avoid floating-point bias), then
        the few hundredths left over from flooring are handed to the categories
        with the largest division remainders. Ties in the remainder break by the
        incoming rank order (count descending, label ascending), so the result is
        fully deterministic. An empty / zero-count dimension yields 0.00% rows.
        """
        total = sum(count for _, count in ranked)
        if total <= 0:
            return [CategoryShare(value=value, count=count, percentage=0.0) for value, count in ranked]

        # Floor each share to whole hundredths-of-a-percent and remember the
        # division remainder so the leftover units can be apportioned fairly.
        floored_hundredths: list[int] = []
        remainders: list[int] = []
        for _, count in ranked:
            scaled = count * _PERCENT_HUNDREDTHS
            floored_hundredths.append(scaled // total)
            remainders.append(scaled % total)

        # Exact percentages sum to 100.00, so flooring loses this many hundredths;
        # give them to the rows with the largest remainders (rank order on ties).
        leftover = _PERCENT_HUNDREDTHS - sum(floored_hundredths)
        rows_by_remainder = sorted(range(len(ranked)), key=lambda i: (-remainders[i], i))
        for i in rows_by_remainder[:leftover]:
            floored_hundredths[i] += 1

        return [
            CategoryShare(value=value, count=count, percentage=hundredths / 100)
            for (value, count), hundredths in zip(ranked, floored_hundredths)
        ]
