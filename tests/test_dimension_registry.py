"""Tests for the dimension registry and ``build_dimensions`` factory."""

from __future__ import annotations

import pytest

from logstats.dimensions import DIMENSION_REGISTRY, build_dimensions


def test_build_dimensions_from_registry(fake_country_resolver, fake_user_agent_resolver) -> None:
    dimensions = build_dimensions(
        ["country", "os", "browser"], fake_country_resolver, fake_user_agent_resolver
    )
    assert [d.name for d in dimensions] == ["Country", "OS", "Browser"]


def test_build_dimensions_rejects_unknown(fake_country_resolver, fake_user_agent_resolver) -> None:
    with pytest.raises(KeyError):
        build_dimensions(["nope"], fake_country_resolver, fake_user_agent_resolver)


def test_registry_exposes_expected_keys() -> None:
    assert {"country", "os", "browser", "method", "status"} <= set(DIMENSION_REGISTRY)
