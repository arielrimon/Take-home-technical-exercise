"""Shared test fixtures and lightweight fakes.

The fakes implement the resolver protocols with in-memory lookup tables so the
analysis logic can be tested deterministically, with no GeoIP database, network
access, or User-Agent library involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from logstats.models import (
    CategoryShare,
    DimensionStatistics,
    LogRecord,
    ParsedUserAgent,
    StatisticalReport,
)

# --- Real dataset locations (git-ignored; fetched locally per the README) -----
# Integration / e2e tests that need real external data use these paths and the
# skip markers below, so the suite stays green even when the data is absent.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
APACHE_LOG_PATH = _DATA_DIR / "apache_log.txt"
GEOIP_DB_PATH = _DATA_DIR / "GeoLite2-Country.mmdb"

requires_geoip = pytest.mark.skipif(
    not GEOIP_DB_PATH.is_file(),
    reason="GeoLite2 database not present in data/ (see README)",
)
requires_dataset = pytest.mark.skipif(
    not (APACHE_LOG_PATH.is_file() and GEOIP_DB_PATH.is_file()),
    reason="real Apache log and/or GeoLite2 database not present in data/ (see README)",
)


class FakeCountryResolver:
    """In-memory ``CountryResolver`` backed by an ``ip -> country`` table."""

    def __init__(self, ip_to_country: dict[str, str | None]) -> None:
        self._ip_to_country = ip_to_country

    def resolve(self, ip: str) -> str | None:
        return self._ip_to_country.get(ip)


class FakeUserAgentResolver:
    """In-memory ``UserAgentResolver`` backed by a ``ua -> (os, browser)`` table."""

    def __init__(self, ua_to_families: dict[str, tuple[str, str]]) -> None:
        self._ua_to_families = ua_to_families

    def resolve(self, user_agent: str) -> ParsedUserAgent:
        os_family, browser_family = self._ua_to_families.get(user_agent, ("Other", "Other"))
        return ParsedUserAgent(os_family=os_family, browser_family=browser_family)


def make_record(*, ip: str = "1.2.3.4", user_agent: str = "ua", method: str = "GET",
                status: int | None = 200) -> LogRecord:
    """Build a minimal valid :class:`LogRecord` for tests that only need a few fields."""
    return LogRecord(
        ip=ip,
        identity="-",
        user="-",
        timestamp_raw=None,
        method=method,
        path="/",
        protocol="HTTP/1.1",
        status=status,
        size=None,
        referer="-",
        user_agent=user_agent,
    )


@pytest.fixture
def fake_country_resolver() -> FakeCountryResolver:
    return FakeCountryResolver(
        {
            "1.1.1.1": "United States",
            "2.2.2.2": "United States",
            "3.3.3.3": "France",
            "9.9.9.9": None,  # known IP that does not resolve
        }
    )


@pytest.fixture
def fake_user_agent_resolver() -> FakeUserAgentResolver:
    return FakeUserAgentResolver(
        {
            "chrome-win": ("Windows", "Chrome"),
            "safari-mac": ("Mac OS X", "Safari"),
            "bot": ("Other", "Other"),
        }
    )


@pytest.fixture
def sample_report() -> StatisticalReport:
    """A small two-dimension report shared across the formatter tests."""
    return StatisticalReport(
        source="sample.log",
        total_lines=100,
        parsed_records=100,
        skipped_lines=0,
        dimensions=[
            DimensionStatistics(
                name="Country",
                total=100,
                shares=[
                    CategoryShare(value="United States", count=70, percentage=70.0),
                    CategoryShare(value="France", count=30, percentage=30.0),
                ],
            ),
            DimensionStatistics(
                name="OS",
                total=100,
                shares=[CategoryShare(value="Windows", count=100, percentage=100.0)],
            ),
        ],
    )
