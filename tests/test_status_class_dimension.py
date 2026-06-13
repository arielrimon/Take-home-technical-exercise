"""Tests for ``StatusClassDimension`` (HTTP status code → 2xx/4xx/... class)."""

from __future__ import annotations

from logstats.dimensions import UNKNOWN_LABEL, StatusClassDimension

from .conftest import make_record


def test_status_class_dimension() -> None:
    dimension = StatusClassDimension()
    assert dimension.extract(make_record(status=200)) == "2xx"
    assert dimension.extract(make_record(status=404)) == "4xx"
    assert dimension.extract(make_record(status=None)) == UNKNOWN_LABEL


def test_status_class_dimension_out_of_range_is_unknown() -> None:
    # Codes outside the valid HTTP 1xx..5xx range (a corrupt 0 or 700) must not
    # produce a nonsensical "0xx"/"7xx" bucket — they collapse to Unknown so the
    # dimension only ever emits the five real classes plus Unknown.
    dimension = StatusClassDimension()
    assert dimension.extract(make_record(status=0)) == UNKNOWN_LABEL
    assert dimension.extract(make_record(status=99)) == UNKNOWN_LABEL
    assert dimension.extract(make_record(status=700)) == UNKNOWN_LABEL
    assert dimension.extract(make_record(status=100)) == "1xx"
    assert dimension.extract(make_record(status=599)) == "5xx"
