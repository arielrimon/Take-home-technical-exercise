"""Tests for ``UapUserAgentResolver``, focusing on its caching behaviour.

Caching is a deliberate performance optimisation (logs repeat the same
User-Agent strings thousands of times), so these tests pin that a repeated
lookup is served from the cache rather than re-parsed.
"""

from __future__ import annotations

from logstats.resolvers import UapUserAgentResolver

_CHROME_ON_WINDOWS = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/32.0.1700.77 Safari/537.36"
)


def test_user_agent_resolver_parses_families() -> None:
    resolver = UapUserAgentResolver()
    parsed = resolver.resolve(_CHROME_ON_WINDOWS)
    assert parsed.os_family == "Windows"
    assert parsed.browser_family == "Chrome"


def test_user_agent_resolver_caches_by_string() -> None:
    resolver = UapUserAgentResolver()
    first = resolver.resolve(_CHROME_ON_WINDOWS)
    second = resolver.resolve(_CHROME_ON_WINDOWS)
    # A cache hit returns the exact same object rather than re-parsing.
    assert first is second


def test_user_agent_resolver_caches_per_unique_string() -> None:
    resolver = UapUserAgentResolver()
    resolver.resolve(_CHROME_ON_WINDOWS)
    resolver.resolve("curl/7.64.1")
    # Exactly one cache entry per distinct User-Agent string.
    assert resolver.cache_info().currsize == 2
