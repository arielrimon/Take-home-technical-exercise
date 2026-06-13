"""The :class:`LogRecord` model — one parsed access-log line."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

# strptime pattern for the Apache time field, e.g. "17/May/2015:10:05:03 +0000".
# Lives here (not in the parser) because the timestamp is parsed lazily by this
# model, on first access, rather than eagerly for every line — see ``timestamp``.
_APACHE_TIME_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


class LogRecord(BaseModel):
    """One Apache "combined" log line decomposed into its individual fields.

    This is the canonical, transport-agnostic representation of a single HTTP
    request. Parsers produce it and dimensions consume it, so neither side has
    to know anything about the raw text layout of the log.

    The timestamp is held as its raw string and parsed **lazily** via the
    :attr:`timestamp` property: ``datetime.strptime`` is one of the most
    expensive calls on the per-line hot path, and none of the shipped dimensions
    (country / OS / browser / status / method) read the timestamp at all, so
    parsing it eagerly for every line was pure wasted CPU at scale.
    """

    model_config = ConfigDict(frozen=True)

    ip: str
    """Client IP address (the ``%h`` field); used for geo-location."""

    identity: str
    """RFC 1413 identity (``%l``); almost always ``-`` in practice."""

    user: str
    """Authenticated user name (``%u``); ``-`` when no auth was performed."""

    timestamp_raw: str | None
    """Raw Apache time field (e.g. ``17/May/2015:10:05:03 +0000``), or ``None``.

    Parsed on demand by :attr:`timestamp`; kept as text so the hot path never
    pays the ``strptime`` cost for a field most reports do not use.
    """

    method: str
    """HTTP method extracted from the request line (e.g. ``GET``)."""

    path: str
    """Request target/path extracted from the request line."""

    protocol: str
    """Protocol token from the request line (e.g. ``HTTP/1.1``)."""

    status: int | None
    """HTTP status code (``%>s``). ``None`` when absent (logged as ``-``)."""

    size: int | None
    """Response size in bytes (``%b``). ``None`` when logged as ``-``."""

    referer: str
    """``Referer`` request header (``-`` when not sent)."""

    user_agent: str
    """``User-Agent`` request header; used to derive OS and browser."""

    @property
    def timestamp(self) -> datetime | None:
        """Lazily parse and return the request time, or ``None`` if unparseable.

        Parses :attr:`timestamp_raw` only when a caller actually reads this
        property. Both "no timestamp logged" and "timestamp in an unexpected
        format" map to ``None`` so consumers can treat a missing time uniformly.
        """
        if self.timestamp_raw is None:
            return None
        try:
            return datetime.strptime(self.timestamp_raw, _APACHE_TIME_FORMAT)
        except ValueError:
            return None
