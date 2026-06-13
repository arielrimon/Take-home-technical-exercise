"""Application service package — the reusable composition root for the library.

This is where the pieces are wired together, deliberately *outside* the CLI. Any
front-end — the bundled CLI, an HTTP API, a notebook, a scheduled job — drives
the library through here instead of re-assembling parser + resolvers +
dimensions + pipeline itself.

Layout:

* :mod:`logstats.service.report_service` — ``StatisticsReportService`` (reusable, holds resolvers)
* :mod:`logstats.service.analyze`        — ``analyze_log_file`` (one-shot, manages all I/O)
* :mod:`logstats.service.parallel`       — ``analyze_log_file_parallel`` (shard across processes)
* :mod:`logstats.service.render`         — ``render_report`` (report → string in any format)

Example — a different front-end (e.g. a web handler) in a few lines::

    service = StatisticsReportService.from_geoip_path("GeoLite2-Country.mmdb")
    report = service.generate(open("access.log"), source="access.log")
    return report.model_dump()            # JSON-ready, no formatting needed
"""

from logstats.service.analyze import analyze_log_file
from logstats.service.parallel import analyze_log_file_parallel
from logstats.service.render import render_report
from logstats.service.report_service import StatisticsReportService

__all__ = [
    "StatisticsReportService",
    "analyze_log_file",
    "analyze_log_file_parallel",
    "render_report",
]
