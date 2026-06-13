"""Integration tests — real components wired together (no fakes).

These exercise the genuine collaborators (the regex parser, the ``user_agents``
library, the MaxMind reader, the streaming aggregator) through the real
pipeline. Tests that need the git-ignored GeoIP database / log file are skipped
when those are absent; the User-Agent path needs no external data and always runs.
"""

from __future__ import annotations

from logstats.dimensions import BrowserDimension, CountryDimension, OperatingSystemDimension
from logstats.parsing import ApacheCombinedLogParser
from logstats.pipeline import ReportPipeline
from logstats.resolvers import MaxMindCountryResolver, UapUserAgentResolver
from logstats.service import analyze_log_file

from .conftest import APACHE_LOG_PATH, GEOIP_DB_PATH, make_record, requires_dataset

# Real log lines taken from the dataset, covering distinct OS/browser families
# plus the genuinely malformed (unterminated User-Agent quote) line.
_REAL_LINES = [
    # Chrome on Mac OS X
    '83.149.9.216 - - [17/May/2015:10:05:03 +0000] "GET /a HTTP/1.1" 200 1 "-" '
    '"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/32.0.1700.77 Safari/537.36"',
    # Chrome on Windows
    '1.2.3.4 - - [17/May/2015:10:05:04 +0000] "GET /b HTTP/1.1" 200 1 "-" '
    '"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/32.0.1700.77 Safari/537.36"',
    # Unrecognised agent -> Unknown / Unknown
    '46.105.14.53 - - [20/May/2015:21:05:15 +0000] "GET /c HTTP/1.1" 200 1 "-" '
    '"UniversalFeedParser/4.2-pre-314-svn +http://feedparser.org/"',
    # Malformed: the closing quote of the User-Agent is missing.
    '46.118.127.106 - - [20/May/2015:12:05:17 +0000] "GET /d HTTP/1.1" 200 1 "-" '
    '"Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html',
]


def test_real_user_agent_pipeline_no_external_data() -> None:
    """Real parser + real ``user_agents`` lib + real pipeline over sample lines."""
    user_agent_resolver = UapUserAgentResolver()
    pipeline = ReportPipeline(
        ApacheCombinedLogParser(),
        [OperatingSystemDimension(user_agent_resolver), BrowserDimension(user_agent_resolver)],
    )
    report = pipeline.run(iter(_REAL_LINES), source="sample")

    assert report.total_lines == 4
    assert report.parsed_records == 3  # the truncated line is skipped
    assert report.skipped_lines == 1

    os_stats = {s.value: s.count for s in report.dimensions[0].shares}
    assert os_stats == {"Windows": 1, "Mac OS": 1, "Unknown": 1}

    browser_stats = {s.value: s.count for s in report.dimensions[1].shares}
    assert browser_stats == {"Chrome": 2, "Unknown": 1}


@requires_dataset
def test_full_stack_against_real_dataset() -> None:
    """End-to-end analysis of the real 10k-line log with the real GeoIP DB."""
    report = analyze_log_file(APACHE_LOG_PATH, GEOIP_DB_PATH)

    # Parse accounting: exactly one malformed line in this dataset.
    assert report.total_lines == 10_000
    assert report.parsed_records == 9_999
    assert report.skipped_lines == 1
    assert [d.name for d in report.dimensions] == ["Country", "OS", "Browser"]

    for dimension in report.dimensions:
        # Counts add up to the parsed total for every dimension...
        assert sum(s.count for s in dimension.shares) == report.parsed_records
        # ...so the percentages sum to ~100 (independent rounding aside).
        assert abs(sum(s.percentage for s in dimension.shares) - 100.0) < 1e-6
        # ...and shares are sorted by count descending.
        counts = [s.count for s in dimension.shares]
        assert counts == sorted(counts, reverse=True)

    # Stable, data-driven expectations (loose enough to survive GeoIP DB version
    # differences): the US dominates traffic, Windows leads OS, Chrome appears.
    country = report.dimensions[0]
    assert country.shares[0].value == "United States"
    assert country.shares[0].percentage > 25.0

    os_values = [s.value for s in report.dimensions[1].shares]
    assert os_values[0] == "Windows"

    browser_values = [s.value for s in report.dimensions[2].shares]
    assert "Chrome" in browser_values


@requires_dataset
def test_full_stack_top_n_adds_other_bucket() -> None:
    """With top-n, every dimension that overflows gains a single 'Other' row."""
    report = analyze_log_file(APACHE_LOG_PATH, GEOIP_DB_PATH, dimensions=["country"], top_n=5)
    country = report.dimensions[0]
    assert len(country.shares) == 6  # 5 kept + Other
    assert country.shares[-1].value == "Other"
    assert sum(s.count for s in country.shares) == report.parsed_records


@requires_dataset
def test_country_dimension_with_real_resolver() -> None:
    """Real MaxMind resolver resolves a known dataset IP to its country."""
    with MaxMindCountryResolver(GEOIP_DB_PATH) as resolver:
        dimension = CountryDimension(resolver)
        assert dimension.extract(make_record(ip="8.8.8.8")) == "United States"
