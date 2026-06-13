"""One-shot file analysis helper that manages all I/O for a single run."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path

from logstats.dimensions import DEFAULT_DIMENSION_KEYS
from logstats.models import StatisticalReport
from logstats.parsing import LogParser
from logstats.service.report_service import StatisticsReportService


def analyze_log_file(
    log_path: str | Path,
    geoip_database_path: str | Path,
    *,
    dimensions: Sequence[str] = DEFAULT_DIMENSION_KEYS,
    top_n: int | None = None,
    parser: LogParser | None = None,
) -> StatisticalReport:
    """Analyse a log file end-to-end and return the report, managing all I/O.

    Opens the GeoIP database and the log file, runs a single analysis, and
    guarantees both are closed afterwards (via an :class:`~contextlib.ExitStack`).
    This is the one call a simple front-end or script needs.
    """
    with ExitStack() as resources:
        service = resources.enter_context(
            StatisticsReportService.from_geoip_path(geoip_database_path, parser)
        )
        log_stream = resources.enter_context(
            Path(log_path).open("r", encoding="utf-8", errors="replace")
        )
        return service.generate(
            log_stream, source=str(log_path), dimensions=dimensions, top_n=top_n
        )
