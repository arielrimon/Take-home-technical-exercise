"""The Browser dimension — buckets a request by the browser in its User-Agent."""

from __future__ import annotations

from logstats.dimensions.base import normalise_unknown
from logstats.models import LogRecord
from logstats.resolvers import UserAgentResolver


class BrowserDimension:
    """Buckets a request by the browser family parsed from its User-Agent."""

    name = "Browser"

    def __init__(self, user_agent_resolver: UserAgentResolver) -> None:
        self._user_agent_resolver = user_agent_resolver

    def extract(self, record: LogRecord) -> str:
        """Return the browser family for ``record``'s User-Agent."""
        return normalise_unknown(self._user_agent_resolver.resolve(record.user_agent).browser_family)
