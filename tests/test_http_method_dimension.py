"""Tests for ``HttpMethodDimension`` (request method → label)."""

from __future__ import annotations

from logstats.dimensions import UNKNOWN_LABEL, HttpMethodDimension

from .conftest import make_record


def test_http_method_dimension() -> None:
    dimension = HttpMethodDimension()
    assert dimension.extract(make_record(method="POST")) == "POST"
    assert dimension.extract(make_record(method="")) == UNKNOWN_LABEL
