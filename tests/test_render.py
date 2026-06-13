"""Tests for ``render_report`` — the service-level format dispatch helper."""

from __future__ import annotations

import json

from logstats.service import StatisticsReportService, render_report

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


def test_render_report_text_and_json_are_consistent() -> None:
    report = _service().generate(iter(LINES), source="t", dimensions=["country"])

    text = render_report(report, "text")
    assert "Country:" in text
    assert "United States 50.00%" in text

    payload = json.loads(render_report(report, "json"))
    assert payload["parsed_records"] == 2
    assert payload["dimensions"][0]["name"] == "Country"
