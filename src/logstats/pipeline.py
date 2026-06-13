"""Pipeline: the orchestrator that wires parsing and aggregation together.

:class:`ReportPipeline` owns the end-to-end flow over a stream of lines:

    read line -> parse (skip + count malformed) -> aggregate -> build report

It depends only on the :class:`LogParser` and :class:`Dimension` abstractions,
so it is agnostic to *which* log format is parsed or *which* statistics are
computed. Reading the file and choosing concrete implementations is the job of
the composition root (see :mod:`logstats.cli`), keeping I/O and wiring out of
the analysis core.

The per-line loop is split into a timed :meth:`ReportPipeline.aggregate` pass
and a separate :func:`build_report` step. That seam is what lets the parallel
orchestrator (:mod:`logstats.parallel`) reuse the *exact same* report assembly:
each worker runs an ``aggregate`` pass over its shard, and the orchestrator
merges the resulting counters and calls :func:`build_report` once.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter

from logstats.aggregation import DEFAULT_OTHER_LABEL, DimensionAggregator
from logstats.dimensions import Dimension
from logstats.models import StageTimings, StatisticalReport
from logstats.parsing import LogParseError, LogParser

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AggregationPass:
    """The result of one aggregation pass: the tally plus its accounting.

    A small internal carrier (not a Pydantic model) because it holds a live
    :class:`DimensionAggregator`, which is not a serialisable value. It is the
    shared currency between :meth:`ReportPipeline.aggregate` and
    :func:`build_report`, and the parallel orchestrator constructs one from
    merged worker shards before calling :func:`build_report`.
    """

    aggregator: DimensionAggregator
    total_lines: int
    skipped_lines: int
    timings: StageTimings


def build_report(
    source: str,
    result: AggregationPass,
    *,
    top_n: int | None = None,
    other_label: str = DEFAULT_OTHER_LABEL,
) -> StatisticalReport:
    """Render a completed :class:`AggregationPass` into a :class:`StatisticalReport`.

    Shared by the sequential pipeline and the parallel orchestrator so both emit
    the same report shape and the same one-line timing summary. The summary is
    logged at INFO with the stage breakdown attached as structured ``extra``
    fields, so a ``--verbose`` run reveals whether a workload is read-bound,
    parse-bound or lookup-bound — the signal that says whether more processes
    would help.
    """
    aggregator = result.aggregator
    report = StatisticalReport(
        source=source,
        total_lines=result.total_lines,
        parsed_records=aggregator.record_count,
        skipped_lines=result.skipped_lines,
        dimensions=aggregator.results(top_n=top_n, other_label=other_label),
    )

    timings = result.timings
    logger.info(
        "analysed %s: %d/%d lines parsed, %d skipped, %d dimensions in %.4fs "
        "(read %.4fs, parse %.4fs, aggregate %.4fs)",
        source,
        report.parsed_records,
        result.total_lines,
        result.skipped_lines,
        aggregator.dimension_count,
        timings.total_seconds,
        timings.read_seconds,
        timings.parse_seconds,
        timings.aggregate_seconds,
        extra={
            "source": source,
            "total_lines": result.total_lines,
            "parsed_records": report.parsed_records,
            "skipped_lines": result.skipped_lines,
            "dimension_count": aggregator.dimension_count,
            **timings.as_log_extra(),
        },
    )
    return report


class ReportPipeline:
    """Coordinates parsing and aggregation to produce a :class:`StatisticalReport`."""

    def __init__(
        self,
        parser: LogParser,
        dimensions: list[Dimension],
        *,
        top_n: int | None = None,
        other_label: str = DEFAULT_OTHER_LABEL,
        collect_timings: bool | None = None,
    ) -> None:
        """Capture the parsing strategy, dimensions, and reporting options.

        ``top_n`` (when set) limits each dimension to its N most frequent
        categories, collapsing the rest into the ``other_label`` bucket.

        ``collect_timings`` controls the per-stage profiling in
        :meth:`aggregate`: ``None`` (default) auto-enables it only when an INFO
        summary will actually be emitted (i.e. ``--verbose``), so a normal run
        never pays the per-line clock cost; ``True``/``False`` force it on/off
        (the parallel workers pass an explicit value so a verbose parallel run
        still gets its stage breakdown).
        """
        self._parser = parser
        self._dimensions = dimensions
        self._top_n = top_n
        self._other_label = other_label
        self._collect_timings = collect_timings

    def run(self, lines: Iterable[str], source: str) -> StatisticalReport:
        """Analyse ``lines`` and return the assembled report.

        Each line is parsed independently; a :class:`LogParseError` causes that
        single line to be skipped and counted (so one malformed entry never
        aborts the run). Blank lines are ignored entirely and not counted. The
        whole pass is timed (per stage) and summarised in a single log record.
        """
        result = self.aggregate(lines)
        return build_report(
            source, result, top_n=self._top_n, other_label=self._other_label
        )

    def aggregate(self, lines: Iterable[str]) -> AggregationPass:
        """Run the per-line loop once and return the tally plus line accounting.

        Returns the populated :class:`DimensionAggregator` rather than a finished
        report, so callers can either render it directly (:meth:`run`) or merge
        several passes first (the parallel path).

        The per-stage timing samples the clock up to three times *per line*,
        which is millions of ``perf_counter`` calls on a large file — pure
        overhead unless someone is actually reading the stage breakdown — so it
        is opt-in (auto-enabled only under ``--verbose``). The single
        :meth:`_aggregate` loop honours that flag internally rather than
        maintaining a separate fast and timed copy of the body.
        """
        collect_timings = self._collect_timings
        if collect_timings is None:
            # Auto: only instrument when the INFO summary that consumes the
            # breakdown will actually be emitted, so the default run stays lean.
            collect_timings = logger.isEnabledFor(logging.INFO)
        return self._aggregate(lines, timed=collect_timings)

    def _aggregate(self, lines: Iterable[str], *, timed: bool) -> AggregationPass:
        """Run the per-line parse/skip/tally loop once, optionally stage-timed.

        A single loop body serves both the lean default path and the profiling
        path so the parsing / skip-accounting / tallying semantics can never
        drift between them. ``timed`` is a loop-invariant local, so the per-line
        ``if timed`` guards are cheap, predictable branches: when off,
        ``perf_counter`` is sampled only twice (start and end) and the per-stage
        figures stay at zero; when on, the clock is read around each of the three
        stages — ``read`` (advancing the iterator, i.e. file/IPC I/O), ``parse``
        (the regex decode) and ``aggregate`` (GeoIP / UA resolution plus counter
        updates) — so a ``--verbose`` run reveals where the time actually goes.
        """
        aggregator = DimensionAggregator(self._dimensions)
        total_lines = 0
        skipped_lines = 0
        read_seconds = 0.0
        parse_seconds = 0.0
        aggregate_seconds = 0.0

        # Bind the clock locally; on the timed path it is called up to three times
        # per line, so the attribute lookup is worth hoisting out of the hot loop.
        clock = perf_counter
        started_at = clock()
        # Iterate manually (rather than ``for``) so the read step — where file /
        # IPC I/O actually happens — can be timed in isolation on the timed path.
        iterator = iter(lines)
        line_number = 0

        while True:
            # READ — advancing the iterator is where file/IPC I/O actually happens.
            read_start = clock() if timed else 0.0
            try:
                raw_line = next(iterator)
            except StopIteration:
                if timed:
                    read_seconds += clock() - read_start
                break
            if timed:
                read_seconds += clock() - read_start

            line_number += 1
            if not raw_line.strip():
                continue
            total_lines += 1

            # PARSE — regex decode of the raw line into a typed LogRecord.
            parse_start = clock() if timed else 0.0
            try:
                record = self._parser.parse(raw_line)
            except LogParseError:
                if timed:
                    parse_seconds += clock() - parse_start
                skipped_lines += 1
                # Per-line detail stays at DEBUG to avoid flooding normal runs;
                # the aggregate skip count is reported once at the end.
                logger.debug("skipped malformed log line", extra={"line_number": line_number})
                continue
            if timed:
                parse_seconds += clock() - parse_start

            # AGGREGATE — resolve each dimension (GeoIP / UA lookups) and tally.
            if timed:
                aggregate_start = clock()
                aggregator.add(record)
                aggregate_seconds += clock() - aggregate_start
            else:
                aggregator.add(record)

        timings = StageTimings(
            read_seconds=read_seconds,
            parse_seconds=parse_seconds,
            aggregate_seconds=aggregate_seconds,
            total_seconds=clock() - started_at,
        )
        return AggregationPass(
            aggregator=aggregator,
            total_lines=total_lines,
            skipped_lines=skipped_lines,
            timings=timings,
        )
