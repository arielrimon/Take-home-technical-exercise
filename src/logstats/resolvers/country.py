"""IP → country resolution backed by a local MaxMind GeoLite2 database.

Uses the downloadable on-disk ``.mmdb`` database through ``geoip2`` (never the
web API), so lookups are local and not rate-limited. Satisfies the
:class:`logstats.resolvers.base.CountryResolver` protocol structurally.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import geoip2.database
from geoip2.errors import AddressNotFoundError

logger = logging.getLogger(__name__)

# Upper bound on the IP -> country memo. A single large log can contain millions
# of distinct client IPs, so an unbounded cache would grow O(distinct IPs) — the
# real memory ceiling for big files. An LRU keeps memory O(cache size) while
# still serving the hot, frequently-recurring addresses from cache; 100k entries
# is a few MB and comfortably covers the working set of a typical access log.
_DEFAULT_IP_CACHE_SIZE = 100_000


class MaxMindCountryResolver:
    """Resolves IP addresses to country names via a MaxMind GeoLite2 ``.mmdb`` file.

    Results are memoised in a bounded (LRU) ``ip -> country`` cache because
    client IPs recur heavily in real traffic, so we pay the binary-tree lookup
    cost once per unique address — while capping memory so the cache cannot grow
    without limit on a log with a huge number of distinct IPs.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        cache_size: int = _DEFAULT_IP_CACHE_SIZE,
    ) -> None:
        """Open the GeoLite2 database at ``database_path`` for reading.

        Raises ``FileNotFoundError`` if the database file does not exist, which
        the CLI surfaces as an actionable message pointing at the README.
        ``cache_size`` bounds the IP memo (least-recently-used eviction).
        """
        self._reader = geoip2.database.Reader(str(database_path))
        # Wrap the actual lookup in a per-instance LRU cache. Binding it here
        # (rather than decorating the method) keeps each resolver's cache its own
        # and bounded by ``cache_size`` entries.
        self._resolve_cached = lru_cache(maxsize=cache_size)(self._lookup_country)

    def resolve(self, ip: str) -> str | None:
        """Return the country name for ``ip`` (LRU-cached), or ``None`` if unknown.

        Both "address not in the database" and "not a valid IP literal" map to
        ``None`` so the caller can treat every unresolved case uniformly.
        """
        return self._resolve_cached(ip)

    def _lookup_country(self, ip: str) -> str | None:
        """Perform the uncached GeoIP lookup for ``ip`` (the cache miss path)."""
        try:
            return self._reader.country(ip).country.name
        except AddressNotFoundError:
            return None
        except ValueError:
            # The IP field was not a parseable address literal.
            logger.debug("invalid IP literal for geo lookup", extra={"ip": ip})
            return None

    def cache_info(self) -> "object":
        """Expose the LRU cache statistics (hits / misses / size) for introspection."""
        return self._resolve_cached.cache_info()

    def close(self) -> None:
        """Close the underlying database reader and release its file handle."""
        self._reader.close()

    def __enter__(self) -> "MaxMindCountryResolver":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
