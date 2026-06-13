"""Parallel analysis — shard the file by byte range, aggregate, merge counters.

This is the scale-out path alluded to in ``DESIGN.md`` §8: the work (parse +
GeoIP/UA resolution) is CPU/lookup-bound and *embarrassingly parallel*, and the
:class:`~logstats.aggregation.DimensionAggregator` already merges by simple
counter addition. So we:

1. Split the file into ``N`` **line-aligned byte ranges** (one per worker).
2. Hand each range to a worker process that reads *its own* slice directly from
   disk (no central reader bottleneck, no shipping log lines over IPC) and runs
   the ordinary :meth:`ReportPipeline.aggregate` pass over it.
3. Merge the workers' :class:`PartialAggregate` counters in the parent and build
   the single final report with the shared :func:`build_report`.

Determinism is preserved: counter addition is associative/commutative, so the
merged totals — and therefore the sorted, tie-broken output — are identical to a
sequential run regardless of how the file was sharded or in what order workers
finish.

Scope: this path requires a **seekable file** and the default construction
(GeoIP path + dimension keys), because the per-worker resolvers are rebuilt from
those primitives — a live injected parser/resolver is not picklable across the
process boundary. Callers wanting a custom parser use the sequential
:func:`logstats.service.analyze.analyze_log_file`.
"""

from __future__ import annotations

import atexit
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from collections.abc import Iterator, Sequence
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel

from logstats.aggregation import DEFAULT_OTHER_LABEL, DimensionAggregator
from logstats.dimensions import DEFAULT_DIMENSION_KEYS, build_dimensions
from logstats.models import PartialAggregate, StageTimings, StatisticalReport
from logstats.parsing import ApacheCombinedLogParser
from logstats.pipeline import AggregationPass, ReportPipeline, build_report
from logstats.resolvers import MaxMindCountryResolver, UapUserAgentResolver
from logstats.service.analyze import analyze_log_file

logger = logging.getLogger(__name__)

# Cut several more shards than workers so the pool can load-balance: with one
# shard per worker, a single skewed shard (long lines, a hot region) becomes a
# straggler that alone sets the wall-clock, leaving the other cores idle. Extra
# shards let fast workers pick up more of them (work-stealing), keeping every
# core busy. The GeoIP DB is still opened once per *worker* (process), not per
# shard, so finer sharding adds only cheap per-shard file-open overhead.
_SHARDS_PER_WORKER = 4


class ByteRange(BaseModel):
    """A half-open ``[start, end)`` byte span of the log file for one worker.

    Both ends sit on a line boundary, so a worker that reads every line whose
    start offset falls in the span consumes each line of the file exactly once
    across all shards — no split lines, no overlap.
    """

    start: int
    end: int


def compute_line_aligned_ranges(path: str | Path, shard_count: int) -> list[ByteRange]:
    """Divide ``path`` into up to ``shard_count`` line-aligned byte ranges.

    Cuts the file at evenly spaced byte offsets, then nudges each cut forward to
    the next line boundary (by discarding the partial line it landed in), so no
    record is ever split across two shards. Returns fewer ranges than requested
    when the file is small or lines are long enough that some cuts coincide; an
    empty file yields a single empty range.
    """
    size = os.path.getsize(path)
    if size == 0 or shard_count <= 1:
        return [ByteRange(start=0, end=size)]

    approximate_span = size / shard_count
    # Boundaries always start at 0 and end at EOF; the interior cuts are aligned
    # to the next newline so every shard begins exactly where the previous ended.
    boundaries = [0]
    with open(path, "rb") as handle:
        for shard_index in range(1, shard_count):
            handle.seek(int(approximate_span * shard_index))
            handle.readline()  # Drop the partial line; the next read starts clean.
            aligned_offset = handle.tell()
            # Skip cuts that fell in the same line as the previous boundary (long
            # lines / tiny files) so we never emit a zero-width or backwards range.
            if boundaries[-1] < aligned_offset < size:
                boundaries.append(aligned_offset)
    boundaries.append(size)

    return [
        ByteRange(start=start, end=end)
        for start, end in zip(boundaries, boundaries[1:])
        if end > start
    ]


# --- Per-worker state -------------------------------------------------------
# Built once per process by the pool initializer and reused for every shard that
# process handles, so the GeoIP database is opened (and its IP cache warmed) once
# per worker rather than once per shard.

_WORKER_LOG_PATH: str | None = None
_WORKER_PIPELINE: ReportPipeline | None = None


def _init_worker(
    log_path: str,
    geoip_database_path: str,
    dimension_keys: list[str],
    collect_timings: bool,
) -> None:
    """Build this worker process's parser, resolvers and pipeline once.

    Runs in the child process at pool start-up. The resolvers (open GeoIP handle,
    UA parser) cannot be pickled from the parent, so each worker constructs its
    own from the picklable primitives passed via ``initargs``. ``collect_timings``
    is passed explicitly (rather than auto-detected) because the worker process
    does not inherit the parent's logging config, so it cannot tell on its own
    whether a verbose stage breakdown was requested.
    """
    global _WORKER_LOG_PATH, _WORKER_PIPELINE
    country_resolver = MaxMindCountryResolver(geoip_database_path)
    # The resolver holds an mmap'd GeoIP file handle. Workers are reused for many
    # shards and torn down when the pool closes, so release the handle explicitly
    # at process exit rather than leaking it until interpreter shutdown.
    atexit.register(country_resolver.close)
    user_agent_resolver = UapUserAgentResolver()
    dimensions = build_dimensions(list(dimension_keys), country_resolver, user_agent_resolver)
    _WORKER_LOG_PATH = log_path
    _WORKER_PIPELINE = ReportPipeline(
        ApacheCombinedLogParser(), dimensions, collect_timings=collect_timings
    )


def _read_byte_range(handle, byte_range: ByteRange) -> Iterator[str]:
    """Yield the decoded lines whose start offset lies within ``byte_range``.

    Reads in binary and decodes per line so the byte offsets stay exact (text-mode
    seeks are not defined for arbitrary offsets). ``errors="replace"`` mirrors the
    sequential reader so undecodable bytes degrade identically rather than raising.
    """
    handle.seek(byte_range.start)
    # ``tell()`` before each read is the offset of the line about to be read; we
    # stop once that start has reached ``end`` — the line beginning just before
    # ``end`` is the last one this shard owns (it ends exactly at the next shard's
    # start), so reading it in full causes no overlap.
    while handle.tell() < byte_range.end:
        raw = handle.readline()
        if not raw:
            break
        yield raw.decode("utf-8", errors="replace")


def _process_byte_range(byte_range: ByteRange) -> PartialAggregate:
    """Aggregate one shard in a worker and return its picklable partial result.

    Reuses the per-process pipeline built by :func:`_init_worker`; the heavy
    lifting (regex parse + GeoIP/UA resolution + counting) is exactly the
    sequential :meth:`ReportPipeline.aggregate`, just over a slice of the file.
    """
    assert _WORKER_PIPELINE is not None and _WORKER_LOG_PATH is not None  # set by initializer
    with open(_WORKER_LOG_PATH, "rb") as handle:
        result = _WORKER_PIPELINE.aggregate(_read_byte_range(handle, byte_range))

    aggregator = result.aggregator
    return PartialAggregate(
        dimension_names=aggregator.dimension_names,
        dimension_to_counts=aggregator.snapshot(),
        record_count=aggregator.record_count,
        total_lines=result.total_lines,
        skipped_lines=result.skipped_lines,
        timings=result.timings,
    )


def analyze_log_file_parallel(
    log_path: str | Path,
    geoip_database_path: str | Path,
    *,
    dimensions: Sequence[str] = DEFAULT_DIMENSION_KEYS,
    top_n: int | None = None,
    workers: int | None = None,
) -> StatisticalReport:
    """Analyse a log file across ``workers`` processes and return the merged report.

    Shards the file into line-aligned byte ranges, aggregates each shard in its
    own process, then merges the per-shard counters into one
    :class:`StatisticalReport`. ``workers`` defaults to the CPU count. Falls back
    to the in-process :func:`analyze_log_file` when there is nothing to gain
    (one effective shard — an empty or tiny file, or ``workers <= 1``), avoiding
    pool start-up cost for inputs that cannot benefit.
    """
    log_path = Path(log_path)
    worker_count = workers if workers and workers > 0 else (os.cpu_count() or 1)
    # Shard finer than the worker count so the pool can work-steal stragglers;
    # ``compute_line_aligned_ranges`` collapses any cuts that coincide, so a small
    # file simply yields fewer ranges (down to the sequential fallback below).
    ranges = compute_line_aligned_ranges(log_path, worker_count * _SHARDS_PER_WORKER)

    if len(ranges) <= 1:
        # A single shard would just be a sequential run wrapped in pool overhead.
        logger.info(
            "parallel analysis fell back to sequential (1 shard) for %s",
            str(log_path),
            extra={"source": str(log_path), "requested_workers": worker_count},
        )
        return analyze_log_file(
            log_path, geoip_database_path, dimensions=dimensions, top_n=top_n
        )

    dimension_keys = list(dimensions)
    # Auto-detect verbose timing here in the parent (where logging is configured)
    # and pass it down, since the workers cannot read the parent's logging level.
    collect_timings = logger.isEnabledFor(logging.INFO)
    started_at = perf_counter()
    partials: list[PartialAggregate] = []
    try:
        with ProcessPoolExecutor(
            max_workers=min(worker_count, len(ranges)),
            initializer=_init_worker,
            initargs=(str(log_path), str(geoip_database_path), dimension_keys, collect_timings),
        ) as executor:
            # ``map`` preserves input order, but ordering is irrelevant to the
            # merge (counter addition is commutative) — we collect every shard.
            partials.extend(executor.map(_process_byte_range, ranges))
    except Exception:
        # Any worker failure (a broken pool, an unpicklable error, an
        # initializer that could not open the GeoIP DB in the child, a crashed
        # process) surfaces here as the map is consumed. Rather than abort the
        # whole run with a raw traceback, log it and fall back to the in-process
        # path, which produces an identical report — just without parallelism.
        logger.exception(
            "parallel analysis failed; falling back to sequential",
            extra={
                "source": str(log_path),
                "worker_count": worker_count,
                "shard_count": len(ranges),
            },
        )
        return analyze_log_file(
            log_path, geoip_database_path, dimensions=dimensions, top_n=top_n
        )

    # Merge: fold every shard's counters into one aggregator, summing the line
    # accounting alongside. ``for_merge`` rebuilds the tally from dimension names
    # only — no resolvers needed in the parent, since the workers already resolved.
    merged = DimensionAggregator.for_merge(partials[0].dimension_names)
    total_lines = 0
    skipped_lines = 0
    for partial in partials:
        merged.merge(partial)
        total_lines += partial.total_lines
        skipped_lines += partial.skipped_lines

    # Roll up the workers' per-stage CPU time under the orchestrator's wall clock;
    # summed-CPU ÷ wall-clock ≈ the parallel speed-up actually achieved.
    timings = StageTimings.combine(
        [partial.timings for partial in partials],
        total_seconds=perf_counter() - started_at,
    )
    logger.info(
        "parallel analysis of %s across %d shards: %d lines, %d skipped",
        str(log_path),
        len(ranges),
        total_lines,
        skipped_lines,
        extra={
            "source": str(log_path),
            "shard_count": len(ranges),
            "worker_count": min(worker_count, len(ranges)),
            "total_lines": total_lines,
            "skipped_lines": skipped_lines,
        },
    )

    result = AggregationPass(
        aggregator=merged,
        total_lines=total_lines,
        skipped_lines=skipped_lines,
        timings=timings,
    )
    return build_report(str(log_path), result, top_n=top_n, other_label=DEFAULT_OTHER_LABEL)
