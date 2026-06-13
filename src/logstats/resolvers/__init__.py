"""Resolvers package — enrich raw log fields using external data sources.

Each resolver lives in its own module (one source of external data per file):

* :mod:`logstats.resolvers.base`       — the ``CountryResolver`` / ``UserAgentResolver`` protocols
* :mod:`logstats.resolvers.country`    — ``MaxMindCountryResolver`` (IP → country, GeoLite2 ``.mmdb``)
* :mod:`logstats.resolvers.user_agent` — ``UapUserAgentResolver`` (User-Agent → OS / browser)

They are re-exported here so callers keep importing from ``logstats.resolvers``.
"""

from logstats.resolvers.base import CountryResolver, UserAgentResolver
from logstats.resolvers.country import MaxMindCountryResolver
from logstats.resolvers.user_agent import UapUserAgentResolver

__all__ = [
    "CountryResolver",
    "MaxMindCountryResolver",
    "UapUserAgentResolver",
    "UserAgentResolver",
]
