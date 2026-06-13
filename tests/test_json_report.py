"""Tests for ``JsonReportFormatter`` (machine-readable rounded payload)."""

from __future__ import annotations

import json

from logstats.reporting import JsonReportFormatter


def test_json_format_roundtrips_and_rounds(sample_report) -> None:
    payload = json.loads(JsonReportFormatter().format(sample_report))
    assert payload["parsed_records"] == 100
    assert payload["dimensions"][0]["name"] == "Country"
    assert payload["dimensions"][0]["shares"][0] == {
        "value": "United States",
        "count": 70,
        "percentage": 70.0,
    }
