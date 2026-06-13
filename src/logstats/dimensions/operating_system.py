"""The OS dimension — buckets a request by the OS family in its User-Agent."""

from __future__ import annotations

from logstats.dimensions.base import normalise_unknown
from logstats.models import LogRecord
from logstats.resolvers import UserAgentResolver

# Cosmetic normalisation of OS-family names to the conventional spelling used in
# the assignment's sample output. Kept as a small, obvious, easily extended map
# rather than scattering string fixups through the code.
_OS_FAMILY_NORMALISATION = {"Mac OS X": "Mac OS"}


class OperatingSystemDimension:
    """Buckets a request by the OS family parsed from its User-Agent."""

    name = "OS"

    def __init__(self, user_agent_resolver: UserAgentResolver) -> None:
        self._user_agent_resolver = user_agent_resolver

    def extract(self, record: LogRecord) -> str:
        """Return the (normalised) OS family for ``record``'s User-Agent."""
        os_family = self._user_agent_resolver.resolve(record.user_agent).os_family
        return normalise_unknown(_OS_FAMILY_NORMALISATION.get(os_family, os_family))
