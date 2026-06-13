"""Tests for ``StatisticsReportService`` (the reusable composition root)."""

from __future__ import annotations

from logstats.models import StatisticalReport
from logstats.service import StatisticsReportService

from .conftest import FakeCountryResolver, FakeUserAgentResolver

LINES = [
    '1.1.1.1 - - [17/May/2015:10:05:03 +0000] "GET /a HTTP/1.1" 200 1 "-" "chrome-win"',
    '2.2.2.2 - - [17/May/2015:10:05:04 +0000] "GET /b HTTP/1.1" 200 1 "-" "safari-mac"',
    "malformed line",
]


def _service() -> StatisticsReportService:
    """A service wired with in-memory fakes — no GeoIP DB or network needed."""
    return StatisticsReportService(
        FakeCountryResolver({"1.1.1.1": "United States", "2.2.2.2": "France"}),
        FakeUserAgentResolver({"chrome-win": ("Windows", "Chrome"), "safari-mac": ("Mac OS X", "Safari")}),
    )


def test_generate_returns_structured_report() -> None:
    report = _service().generate(iter(LINES), source="test", dimensions=["country", "os"])
    assert isinstance(report, StatisticalReport)
    assert report.source == "test"
    assert report.parsed_records == 2
    assert report.skipped_lines == 1
    assert [d.name for d in report.dimensions] == ["Country", "OS"]


def test_generate_uses_default_dimensions() -> None:
    report = _service().generate(iter(LINES), source="test")
    assert [d.name for d in report.dimensions] == ["Country", "OS", "Browser"]


def test_service_is_reusable_across_calls() -> None:
    # The same service (and its resolver caches) serves multiple inputs — the
    # exact property a long-running front-end such as a web server relies on.
    service = _service()
    first = service.generate(iter(LINES), source="a", dimensions=["country"])
    second = service.generate(iter(LINES), source="b", dimensions=["country"])
    assert first.parsed_records == second.parsed_records == 2


def test_close_is_safe_when_resolver_has_no_close() -> None:
    # FakeCountryResolver has no close(); the service must tolerate that.
    with _service() as service:
        service.generate(iter(LINES), source="t", dimensions=["country"])
    # Exiting the context (which calls close()) must not raise.
