"""Tests for ``MaxMindCountryResolver``, focusing on its caching behaviour.

The GeoIP database is git-ignored, so these tests run only when it is present
locally (see README for how to fetch it) and are skipped otherwise.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from logstats.resolvers import MaxMindCountryResolver

_GEOIP_DB = Path(__file__).resolve().parent.parent / "data" / "GeoLite2-Country.mmdb"


@pytest.mark.skipif(not _GEOIP_DB.is_file(), reason="GeoLite2 database not available locally")
def test_country_resolver_resolves_and_caches() -> None:
    with MaxMindCountryResolver(_GEOIP_DB) as resolver:
        first = resolver.resolve("8.8.8.8")
        second = resolver.resolve("8.8.8.8")
        assert first == "United States"
        assert second == "United States"
        # The IP is memoised after the first lookup: the repeat is a cache hit,
        # so exactly one entry was stored and the second call did no DB lookup.
        info = resolver.cache_info()
        assert info.hits == 1
        assert info.misses == 1
        assert info.currsize == 1


@pytest.mark.skipif(not _GEOIP_DB.is_file(), reason="GeoLite2 database not available locally")
def test_country_resolver_unknown_ip_returns_none() -> None:
    with MaxMindCountryResolver(_GEOIP_DB) as resolver:
        # Private-range and bogus addresses are not in the country DB.
        assert resolver.resolve("10.0.0.1") is None
        assert resolver.resolve("not-an-ip") is None
