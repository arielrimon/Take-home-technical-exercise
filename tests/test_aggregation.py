"""Tests for streaming aggregation, sorting, percentages and the Other bucket."""

from __future__ import annotations

from logstats.aggregation import DimensionAggregator
from logstats.dimensions import HttpMethodDimension

from .conftest import make_record


def _method_aggregator() -> DimensionAggregator:
    """Aggregator over a single, resolver-free dimension for focused assertions."""
    return DimensionAggregator([HttpMethodDimension()])


def test_counts_and_percentages_sum_to_total() -> None:
    aggregator = _method_aggregator()
    for method in ["GET", "GET", "GET", "POST"]:
        aggregator.add(make_record(method=method))

    [stats] = aggregator.results()
    assert stats.total == 4
    assert [(s.value, s.count) for s in stats.shares] == [("GET", 3), ("POST", 1)]
    assert stats.shares[0].percentage == 75.0
    assert stats.shares[1].percentage == 25.0


def test_sorted_descending_with_alphabetical_tiebreak() -> None:
    aggregator = _method_aggregator()
    # Equal counts for PUT and DELETE -> alphabetical order (DELETE before PUT).
    for method in ["GET", "GET", "PUT", "DELETE"]:
        aggregator.add(make_record(method=method))

    [stats] = aggregator.results()
    assert [s.value for s in stats.shares] == ["GET", "DELETE", "PUT"]


def test_top_n_collapses_tail_into_other() -> None:
    aggregator = _method_aggregator()
    # 5 distinct methods with descending frequency.
    for method, repeats in [("GET", 10), ("POST", 5), ("PUT", 3), ("DELETE", 2), ("HEAD", 1)]:
        for _ in range(repeats):
            aggregator.add(make_record(method=method))

    [stats] = aggregator.results(top_n=2)
    values = {s.value: s.count for s in stats.shares}
    assert values == {"GET": 10, "POST": 5, "Other": 6}  # 3+2+1 collapsed
    # Kept categories stay frequency-sorted; the residual "Other" bucket is
    # appended last even though its aggregate (6) exceeds POST (5).
    assert [s.value for s in stats.shares] == ["GET", "POST", "Other"]


def test_top_n_noop_when_categories_fit() -> None:
    aggregator = _method_aggregator()
    for method in ["GET", "POST"]:
        aggregator.add(make_record(method=method))

    [stats] = aggregator.results(top_n=5)
    assert [s.value for s in stats.shares] == ["GET", "POST"]
    assert all(s.value != "Other" for s in stats.shares)


def test_top_n_zero_collapses_everything_into_other() -> None:
    # Documents the aggregator's behaviour at the boundary: top_n=0 keeps no
    # category and folds the whole distribution into a single "Other" bucket.
    # (The CLI rejects top_n < 1; this pins the library-level contract.)
    aggregator = _method_aggregator()
    for method in ["GET", "GET", "POST"]:
        aggregator.add(make_record(method=method))

    [stats] = aggregator.results(top_n=0)
    assert [(s.value, s.count) for s in stats.shares] == [("Other", 3)]
    assert stats.shares[0].percentage == 100.0


def test_empty_input_yields_empty_shares() -> None:
    aggregator = _method_aggregator()
    [stats] = aggregator.results()
    assert stats.total == 0
    assert stats.shares == []


def test_percentages_round_to_two_decimals_and_sum_to_exactly_100() -> None:
    # Three equal categories: independent rounding would give 33.33 each (99.99).
    # Largest-remainder rounding must instead make the displayed shares total
    # exactly 100.00, nudging one category to 33.34.
    aggregator = _method_aggregator()
    for method in ["GET", "POST", "PUT"]:
        aggregator.add(make_record(method=method))

    [stats] = aggregator.results()
    percentages = sorted(share.percentage for share in stats.shares)
    assert percentages == [33.33, 33.33, 33.34]
    assert sum(share.percentage for share in stats.shares) == 100.0


def test_percentages_sum_to_100_for_an_awkward_distribution() -> None:
    # A 3/1/1/1/1 split (each single = 14.2857%) is a classic case where naive
    # rounding drifts; the apportioned shares must still total exactly 100.00.
    aggregator = _method_aggregator()
    for method, repeats in [("GET", 3), ("POST", 1), ("PUT", 1), ("DELETE", 1), ("HEAD", 1)]:
        for _ in range(repeats):
            aggregator.add(make_record(method=method))

    [stats] = aggregator.results()
    assert sum(share.percentage for share in stats.shares) == 100.0
    # Every share is reported to at most two decimals.
    assert all(round(share.percentage, 2) == share.percentage for share in stats.shares)
