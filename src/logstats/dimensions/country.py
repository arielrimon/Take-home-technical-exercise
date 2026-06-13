"""The Country dimension — buckets a request by its client IP's country."""

from __future__ import annotations

from logstats.dimensions.base import normalise_unknown
from logstats.models import LogRecord
from logstats.resolvers import CountryResolver


class CountryDimension:
    """Buckets a request by the country its client IP geo-locates to."""

    name = "Country"

    def __init__(self, country_resolver: CountryResolver) -> None:
        self._country_resolver = country_resolver

    def extract(self, record: LogRecord) -> str:
        """Geo-locate ``record.ip`` to a country, or UNKNOWN_LABEL if unresolved."""
        return normalise_unknown(self._country_resolver.resolve(record.ip))
