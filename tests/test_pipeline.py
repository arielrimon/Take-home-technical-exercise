"""End-to-end tests for the pipeline using fakes (no GeoIP DB / network)."""

from __future__ import annotations

from logstats.dimensions import BrowserDimension, CountryDimension, OperatingSystemDimension
from logstats.parsing import ApacheCombinedLogParser
from logstats.pipeline import ReportPipeline

from .conftest import FakeCountryResolver, FakeUserAgentResolver

# Three well-formed lines + one malformed (unterminated UA quote) line.
LINES = [
    '1.1.1.1 - - [17/May/2015:10:05:03 +0000] "GET /a HTTP/1.1" 200 1 "-" "chrome-win"',
    '2.2.2.2 - - [17/May/2015:10:05:04 +0000] "GET /b HTTP/1.1" 200 1 "-" "chrome-win"',
    '3.3.3.3 - - [17/May/2015:10:05:05 +0000] "GET /c HTTP/1.1" 200 1 "-" "safari-mac"',
    "this line is malformed",
    "",  # blank lines are ignored entirely
]


def _build_pipeline(**kwargs) -> ReportPipeline:
    country_resolver = FakeCountryResolver(
        {"1.1.1.1": "United States", "2.2.2.2": "United States", "3.3.3.3": "France"}
    )
    user_agent_resolver = FakeUserAgentResolver(
        {"chrome-win": ("Windows", "Chrome"), "safari-mac": ("Mac OS X", "Safari")}
    )
    dimensions = [
        CountryDimension(country_resolver),
        OperatingSystemDimension(user_agent_resolver),
        BrowserDimension(user_agent_resolver),
    ]
    return ReportPipeline(ApacheCombinedLogParser(), dimensions, **kwargs)


def test_pipeline_counts_parsed_and_skipped() -> None:
    report = _build_pipeline().run(iter(LINES), source="test")
    assert report.total_lines == 4  # blank line not counted
    assert report.parsed_records == 3
    assert report.skipped_lines == 1


def test_pipeline_percentages_per_dimension() -> None:
    report = _build_pipeline().run(iter(LINES), source="test")
    by_name = {d.name: d for d in report.dimensions}

    country = {s.value: round(s.percentage, 2) for s in by_name["Country"].shares}
    assert country == {"United States": 66.67, "France": 33.33}

    os_stats = {s.value: round(s.percentage, 2) for s in by_name["OS"].shares}
    assert os_stats == {"Windows": 66.67, "Mac OS": 33.33}

    browser = {s.value: round(s.percentage, 2) for s in by_name["Browser"].shares}
    assert browser == {"Chrome": 66.67, "Safari": 33.33}


def test_pipeline_top_n_applies() -> None:
    report = _build_pipeline(top_n=1).run(iter(LINES), source="test")
    country = {d.name: d for d in report.dimensions}["Country"]
    # Top-1 keeps United States; France collapses into Other.
    assert [s.value for s in country.shares] == ["United States", "Other"]
