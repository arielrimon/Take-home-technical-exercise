"""Tests for the parallel (shard → merge) analysis path.

The pure-unit tests (byte-range splitting, counter merging, timing roll-up) need
no external data and always run. The equivalence test — that a parallel run
produces byte-for-byte the same report as a sequential one — needs the real
dataset and is skipped when it is absent.
"""

from __future__ import annotations

from pathlib import Path

from logstats.aggregation import DimensionAggregator
from logstats.dimensions import HttpMethodDimension
from logstats.models import PartialAggregate, StageTimings
from logstats.service import analyze_log_file, analyze_log_file_parallel
from logstats.service import parallel as parallel_module
from logstats.service.parallel import (
    ByteRange,
    _read_byte_range,
    compute_line_aligned_ranges,
)

from .conftest import APACHE_LOG_PATH, GEOIP_DB_PATH, make_record, requires_dataset


def _write_lines(path: Path, count: int) -> int:
    """Write ``count`` newline-terminated lines and return the file size in bytes."""
    text = "".join(f"line-{index:04d}\n" for index in range(count))
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


# --- Byte-range splitting ---------------------------------------------------


def test_ranges_are_contiguous_and_cover_whole_file(tmp_path: Path) -> None:
    log_file = tmp_path / "log.txt"
    size = _write_lines(log_file, 100)

    ranges = compute_line_aligned_ranges(log_file, 4)

    # Contiguous and gap-free from 0 to EOF.
    assert ranges[0].start == 0
    assert ranges[-1].end == size
    for current, following in zip(ranges, ranges[1:]):
        assert current.end == following.start


def test_ranges_partition_the_lines_exactly_once(tmp_path: Path) -> None:
    log_file = tmp_path / "log.txt"
    _write_lines(log_file, 100)
    ranges = compute_line_aligned_ranges(log_file, 7)

    # Reading every shard in order must reproduce the original line sequence with
    # no duplicates and no omissions — proof the cuts are truly line-aligned.
    collected: list[str] = []
    with open(log_file, "rb") as handle:
        for byte_range in ranges:
            collected.extend(_read_byte_range(handle, byte_range))

    expected = [f"line-{index:04d}\n" for index in range(100)]
    assert collected == expected


def test_empty_file_yields_single_empty_range(tmp_path: Path) -> None:
    log_file = tmp_path / "empty.txt"
    log_file.write_text("", encoding="utf-8")
    assert compute_line_aligned_ranges(log_file, 8) == [ByteRange(start=0, end=0)]


def test_single_worker_is_one_range(tmp_path: Path) -> None:
    log_file = tmp_path / "log.txt"
    size = _write_lines(log_file, 10)
    assert compute_line_aligned_ranges(log_file, 1) == [ByteRange(start=0, end=size)]


# --- Counter merging --------------------------------------------------------


def _partial_from_records(records: list, dimension: HttpMethodDimension) -> PartialAggregate:
    """Aggregate ``records`` into a one-shard partial, as a worker would return."""
    aggregator = DimensionAggregator([dimension])
    for record in records:
        aggregator.add(record)
    return PartialAggregate(
        dimension_names=aggregator.dimension_names,
        dimension_to_counts=aggregator.snapshot(),
        record_count=aggregator.record_count,
        total_lines=len(records),
        skipped_lines=0,
        timings=StageTimings(read_seconds=0, parse_seconds=0, aggregate_seconds=0, total_seconds=0),
    )


def test_merge_matches_single_pass_aggregation() -> None:
    methods = ["GET", "GET", "POST", "PUT", "GET", "POST", "DELETE", "GET"]
    records = [make_record(method=method) for method in methods]

    # Sequential reference: one aggregator over all records.
    reference = DimensionAggregator([HttpMethodDimension()])
    for record in records:
        reference.add(record)

    # Sharded: split the records into two partials and merge them by name.
    first = _partial_from_records(records[:5], HttpMethodDimension())
    second = _partial_from_records(records[5:], HttpMethodDimension())
    merged = DimensionAggregator.for_merge(first.dimension_names)
    merged.merge(first)
    merged.merge(second)

    assert merged.record_count == reference.record_count
    # Identical sorted/percentage output regardless of how records were sharded.
    assert merged.results() == reference.results()


def test_stage_timings_combine_sums_stages_under_supplied_wall_clock() -> None:
    parts = [
        StageTimings(read_seconds=1, parse_seconds=2, aggregate_seconds=3, total_seconds=6),
        StageTimings(read_seconds=4, parse_seconds=5, aggregate_seconds=6, total_seconds=15),
    ]
    combined = StageTimings.combine(parts, total_seconds=9.5)
    assert (combined.read_seconds, combined.parse_seconds, combined.aggregate_seconds) == (5, 7, 9)
    assert combined.total_seconds == 9.5  # the orchestrator's wall clock, not the sum


# --- End-to-end equivalence (needs the real dataset) ------------------------


@requires_dataset
def test_parallel_matches_sequential_on_real_dataset() -> None:
    """A 4-worker parallel run must produce exactly the sequential report."""
    sequential = analyze_log_file(APACHE_LOG_PATH, GEOIP_DB_PATH)
    parallel = analyze_log_file_parallel(APACHE_LOG_PATH, GEOIP_DB_PATH, workers=4)

    assert parallel.total_lines == sequential.total_lines
    assert parallel.parsed_records == sequential.parsed_records
    assert parallel.skipped_lines == sequential.skipped_lines
    # Dimension order, categories, counts and percentages must all match exactly —
    # the merge is deterministic, so the reports are equal field-for-field.
    assert parallel.dimensions == sequential.dimensions


class _BrokenExecutor:
    """A drop-in ProcessPoolExecutor whose ``map`` fails, simulating a dead pool."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self) -> "_BrokenExecutor":
        return self

    def __exit__(self, *_exc_info: object) -> bool:
        return False

    def map(self, *_args, **_kwargs):
        raise RuntimeError("simulated worker failure")


@requires_dataset
def test_parallel_falls_back_to_sequential_when_workers_fail(monkeypatch) -> None:
    """A worker/pool failure must degrade to the sequential path, not crash.

    The merged report from the fallback must be identical to a direct sequential
    run — the parallel path is purely an optimisation, never a correctness fork.
    """
    monkeypatch.setattr(parallel_module, "ProcessPoolExecutor", _BrokenExecutor)

    result = analyze_log_file_parallel(APACHE_LOG_PATH, GEOIP_DB_PATH, workers=4)
    sequential = analyze_log_file(APACHE_LOG_PATH, GEOIP_DB_PATH)

    assert result.parsed_records == sequential.parsed_records
    assert result.dimensions == sequential.dimensions
