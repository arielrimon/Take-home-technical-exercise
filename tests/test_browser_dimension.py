"""Tests for ``BrowserDimension`` (User-Agent → browser-family label)."""

from __future__ import annotations

from logstats.dimensions import UNKNOWN_LABEL, BrowserDimension

from .conftest import make_record


def test_browser_dimension(fake_user_agent_resolver) -> None:
    dimension = BrowserDimension(fake_user_agent_resolver)
    assert dimension.extract(make_record(user_agent="chrome-win")) == "Chrome"
    assert dimension.extract(make_record(user_agent="bot")) == UNKNOWN_LABEL
