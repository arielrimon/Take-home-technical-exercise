"""Tests for ``OperatingSystemDimension`` (User-Agent → OS-family label)."""

from __future__ import annotations

from logstats.dimensions import UNKNOWN_LABEL, OperatingSystemDimension

from .conftest import make_record


def test_os_dimension_normalises_mac_os_x(fake_user_agent_resolver) -> None:
    dimension = OperatingSystemDimension(fake_user_agent_resolver)
    # "Mac OS X" from the library is normalised to "Mac OS".
    assert dimension.extract(make_record(user_agent="safari-mac")) == "Mac OS"


def test_os_dimension_other_becomes_unknown(fake_user_agent_resolver) -> None:
    dimension = OperatingSystemDimension(fake_user_agent_resolver)
    assert dimension.extract(make_record(user_agent="bot")) == UNKNOWN_LABEL
