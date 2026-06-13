"""Tests for ``CountryDimension`` (IP → country-name label extraction)."""

from __future__ import annotations

from logstats.dimensions import UNKNOWN_LABEL, CountryDimension

from .conftest import make_record


def test_country_dimension_resolves_known_ip(fake_country_resolver) -> None:
    dimension = CountryDimension(fake_country_resolver)
    assert dimension.extract(make_record(ip="1.1.1.1")) == "United States"


def test_country_dimension_unknown_ip_becomes_unknown(fake_country_resolver) -> None:
    dimension = CountryDimension(fake_country_resolver)
    # IP absent from the table and IP present-but-unresolved both -> Unknown.
    assert dimension.extract(make_record(ip="8.8.8.8")) == UNKNOWN_LABEL
    assert dimension.extract(make_record(ip="9.9.9.9")) == UNKNOWN_LABEL
