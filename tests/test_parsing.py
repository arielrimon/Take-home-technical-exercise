"""Tests for the Apache combined-log parser."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from logstats.parsing import ApacheCombinedLogParser, LogParseError

# A canonical, well-formed line straight from the assignment description.
SAMPLE_LINE = (
    '83.149.9.216 - - [17/May/2015:10:05:03 +0000] '
    '"GET /presentations/logstash.pdf HTTP/1.1" 200 3478 '
    '"-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/32.0.1700.77 Safari/537.36"'
)


@pytest.fixture
def parser() -> ApacheCombinedLogParser:
    return ApacheCombinedLogParser()


def test_parses_all_fields(parser: ApacheCombinedLogParser) -> None:
    record = parser.parse(SAMPLE_LINE)
    assert record.ip == "83.149.9.216"
    assert record.method == "GET"
    assert record.path == "/presentations/logstash.pdf"
    assert record.protocol == "HTTP/1.1"
    assert record.status == 200
    assert record.size == 3478
    assert record.referer == "-"
    assert "Chrome/32.0.1700.77" in record.user_agent
    assert record.timestamp == datetime(2015, 5, 17, 10, 5, 3, tzinfo=timezone.utc)


def test_dash_size_becomes_none(parser: ApacheCombinedLogParser) -> None:
    line = SAMPLE_LINE.replace(" 200 3478 ", " 304 - ")
    record = parser.parse(line)
    assert record.status == 304
    assert record.size is None


def test_truncated_unterminated_quote_raises(parser: ApacheCombinedLogParser) -> None:
    # The real dataset contains one such line: the user-agent's closing quote is
    # missing, so the line is structurally malformed and must be rejected.
    malformed = (
        '46.118.127.106 - - [20/May/2015:12:05:17 +0000] '
        '"GET /scripts/grok-py-test/configlib.py HTTP/1.1" 200 235 "-" '
        '"Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html'
    )
    with pytest.raises(LogParseError):
        parser.parse(malformed)


def test_garbage_line_raises(parser: ApacheCombinedLogParser) -> None:
    with pytest.raises(LogParseError):
        parser.parse("this is not a log line")


def test_escaped_quote_inside_user_agent(parser: ApacheCombinedLogParser) -> None:
    # A backslash-escaped quote inside the UA must not terminate the field early.
    line = (
        '1.2.3.4 - - [17/May/2015:10:05:03 +0000] "GET / HTTP/1.1" 200 1 '
        '"-" "Weird\\"Agent/1.0"'
    )
    record = parser.parse(line)
    assert record.user_agent == 'Weird\\"Agent/1.0'


def test_unparseable_timestamp_degrades_to_none(parser: ApacheCombinedLogParser) -> None:
    line = SAMPLE_LINE.replace("17/May/2015:10:05:03 +0000", "not-a-date")
    record = parser.parse(line)
    assert record.timestamp is None
    # The rest of the record is still usable.
    assert record.ip == "83.149.9.216"
