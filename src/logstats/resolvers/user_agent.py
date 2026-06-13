"""User-Agent → OS / browser resolution backed by the ``user_agents`` library.

A single User-Agent string feeds *both* the OS and the browser dimension, so
parsing it once in this shared, cached resolver avoids redundant work. Satisfies
the :class:`logstats.resolvers.base.UserAgentResolver` protocol structurally.
"""

from __future__ import annotations

from functools import lru_cache

from user_agents import parse as parse_user_agent

from logstats.models import ParsedUserAgent

# Upper bound on the User-Agent memo. Distinct UA strings are far fewer than
# distinct IPs but can still reach tens of thousands on a busy, bot-heavy log, so
# the cache is bounded (LRU) to keep memory O(cache size) rather than growing
# with every unique string ever seen across an arbitrarily large file.
_DEFAULT_UA_CACHE_SIZE = 50_000


class UapUserAgentResolver:
    """Resolves User-Agent strings to OS / browser families via ``user_agents``.

    Parsing a User-Agent string is comparatively expensive and the same string
    appears many times in a log, so each unique string is parsed once and the
    result served from a bounded (LRU) ``user_agent -> ParsedUserAgent`` cache —
    capping memory while still absorbing the heavy repetition of real traffic.
    """

    def __init__(self, *, cache_size: int = _DEFAULT_UA_CACHE_SIZE) -> None:
        """Set up the resolver with a bounded LRU parse cache of ``cache_size``."""
        # Bind a per-instance LRU around the real parse so each resolver keeps
        # its own cache, capped at ``cache_size`` distinct User-Agent strings.
        self._resolve_cached = lru_cache(maxsize=cache_size)(self._parse_user_agent)

    def resolve(self, user_agent: str) -> ParsedUserAgent:
        """Return the OS / browser families for ``user_agent`` (LRU-cached)."""
        return self._resolve_cached(user_agent)

    @staticmethod
    def _parse_user_agent(user_agent: str) -> ParsedUserAgent:
        """Parse a User-Agent string into its OS / browser families (cache miss)."""
        parsed = parse_user_agent(user_agent)
        return ParsedUserAgent(
            os_family=parsed.os.family,
            browser_family=parsed.browser.family,
        )

    def cache_info(self) -> "object":
        """Expose the LRU cache statistics (hits / misses / size) for introspection."""
        return self._resolve_cached.cache_info()
