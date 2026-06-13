"""The :class:`StatisticsReportService` — wires the pipeline from collaborators.

The service owns *no* I/O of its own: it is constructed with ready resolvers
(and, optionally, a custom parser), which makes it cheap to reuse across many
inputs and trivial to unit-test with fakes. A long-running front-end (e.g. a web
server) builds **one** of these at start-up so the GeoIP database is opened once
and resolver caches are shared across many requests.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from logstats.dimensions import DEFAULT_DIMENSION_KEYS, build_dimensions
from logstats.models import StatisticalReport
from logstats.parsing import ApacheCombinedLogParser, LogParser
from logstats.pipeline import ReportPipeline
from logstats.resolvers import (
    CountryResolver,
    MaxMindCountryResolver,
    UapUserAgentResolver,
    UserAgentResolver,
)


class StatisticsReportService:
    """Wires the analysis pipeline from injected collaborators and runs it."""

    def __init__(
        self,
        country_resolver: CountryResolver,
        user_agent_resolver: UserAgentResolver | None = None,
        parser: LogParser | None = None,
    ) -> None:
        """Capture the resolvers and parser used for every subsequent report."""
        self._country_resolver = country_resolver
        self._user_agent_resolver = user_agent_resolver or UapUserAgentResolver()
        self._parser = parser or ApacheCombinedLogParser()

    @classmethod
    def from_geoip_path(
        cls,
        geoip_database_path: str | Path,
        parser: LogParser | None = None,
    ) -> "StatisticsReportService":
        """Build a service that owns a MaxMind resolver opened from a ``.mmdb`` path.

        Convenience for callers that just have a database path. The returned
        service keeps the database open; use :meth:`close` (or a ``with`` block)
        to release it.
        """
        return cls(MaxMindCountryResolver(geoip_database_path), parser=parser)

    def generate(
        self,
        lines: Iterable[str],
        *,
        source: str,
        dimensions: Sequence[str] = DEFAULT_DIMENSION_KEYS,
        top_n: int | None = None,
    ) -> StatisticalReport:
        """Analyse ``lines`` and return the structured :class:`StatisticalReport`.

        ``dimensions`` are dimension registry keys (e.g. ``["country", "os"]``);
        they are resolved against this service's resolvers. ``top_n`` optionally
        collapses each dimension's long tail into an "Other" bucket.
        """
        built_dimensions = build_dimensions(
            list(dimensions), self._country_resolver, self._user_agent_resolver
        )
        pipeline = ReportPipeline(self._parser, built_dimensions, top_n=top_n)
        return pipeline.run(lines, source=source)

    def close(self) -> None:
        """Release resolver resources (e.g. the GeoIP database file handle)."""
        closer = getattr(self._country_resolver, "close", None)
        if callable(closer):
            closer()

    def __enter__(self) -> "StatisticsReportService":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
