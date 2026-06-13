"""The dimension registry — the seam that makes dimensions selectable by name.

Each entry is a factory that receives the available resolvers and returns a
:class:`Dimension`; resolver-free dimensions simply ignore the arguments. Adding
a new dimension to the CLI/library is one registration line here.
"""

from __future__ import annotations

from collections.abc import Callable

from logstats.dimensions.base import Dimension
from logstats.dimensions.browser import BrowserDimension
from logstats.dimensions.country import CountryDimension
from logstats.dimensions.http_method import HttpMethodDimension
from logstats.dimensions.operating_system import OperatingSystemDimension
from logstats.dimensions.status_class import StatusClassDimension
from logstats.resolvers import CountryResolver, UserAgentResolver

DimensionFactory = Callable[[CountryResolver, UserAgentResolver], Dimension]

DIMENSION_REGISTRY: dict[str, DimensionFactory] = {
    "country": lambda country, _ua: CountryDimension(country),
    "os": lambda _country, ua: OperatingSystemDimension(ua),
    "browser": lambda _country, ua: BrowserDimension(ua),
    "method": lambda _country, _ua: HttpMethodDimension(),
    "status": lambda _country, _ua: StatusClassDimension(),
}

# The three dimensions the assignment asks for, used as the CLI default.
DEFAULT_DIMENSION_KEYS = ("country", "os", "browser")


def build_dimensions(
    keys: list[str],
    country_resolver: CountryResolver,
    user_agent_resolver: UserAgentResolver,
) -> list[Dimension]:
    """Instantiate the dimensions named in ``keys`` using the given resolvers.

    Raises ``KeyError`` (with the offending key) if an unknown dimension is
    requested, so the CLI can report it clearly instead of silently ignoring it.
    """
    dimensions: list[Dimension] = []
    for key in keys:
        try:
            factory = DIMENSION_REGISTRY[key]
        except KeyError:
            raise KeyError(key) from None
        dimensions.append(factory(country_resolver, user_agent_resolver))
    return dimensions
