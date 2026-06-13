"""The :class:`ParsedUserAgent` model — OS / browser distilled from a UA string."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ParsedUserAgent(BaseModel):
    """The OS and browser families distilled from a raw User-Agent string.

    Kept separate from :class:`~logstats.models.log_record.LogRecord` because a
    single User-Agent string is parsed once and reused by every UA-derived
    dimension (OS, browser, ...).
    """

    model_config = ConfigDict(frozen=True)

    os_family: str
    """Operating-system family, e.g. ``Windows``, ``Mac OS``, ``Linux``."""

    browser_family: str
    """Browser family, e.g. ``Chrome``, ``Firefox``, ``Safari``."""
