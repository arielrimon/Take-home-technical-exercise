"""Resolver protocols — the enrichment interfaces that dimensions depend on.

A *resolver* encapsulates one external data source and the cost of querying it.
Keeping these as :class:`typing.Protocol` interfaces (rather than concrete
classes) lets dimensions stay decoupled from *how* a value is resolved, and lets
tests substitute trivial in-memory fakes. Concrete implementations live in
sibling modules (``country.py``, ``user_agent.py``).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from logstats.models import ParsedUserAgent


@runtime_checkable
class CountryResolver(Protocol):
    """Strategy that resolves an IP address to a country name (or ``None``)."""

    def resolve(self, ip: str) -> str | None:
        """Return the country name for ``ip``, or ``None`` if it is unknown."""
        ...


@runtime_checkable
class UserAgentResolver(Protocol):
    """Strategy that resolves a User-Agent string to OS / browser families."""

    def resolve(self, user_agent: str) -> ParsedUserAgent:
        """Return the :class:`ParsedUserAgent` for ``user_agent``."""
        ...
