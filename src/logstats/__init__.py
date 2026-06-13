"""logstats — an extensible statistical reporting module for Apache access logs.

The package is organised as a small pipeline of single-responsibility,
interface-driven components:

* :mod:`logstats.parsing`     — ``LogParser``: raw line -> ``LogRecord``
* :mod:`logstats.resolvers`   — ``CountryResolver`` / ``UserAgentResolver``: enrich fields
* :mod:`logstats.dimensions`  — ``Dimension``: record -> category label (extension point)
* :mod:`logstats.aggregation` — ``DimensionAggregator``: streaming frequency counts
* :mod:`logstats.reporting`   — ``ReportFormatter``: report -> text / JSON / CSV (extension point)
* :mod:`logstats.pipeline`    — ``ReportPipeline``: wires the stages together
* :mod:`logstats.cli`         — command-line composition root

The public names below are the stable surface for embedding the module in
other code.
"""

from logstats.aggregation import DimensionAggregator
from logstats.dimensions import (
    BrowserDimension,
    CountryDimension,
    Dimension,
    OperatingSystemDimension,
    build_dimensions,
)
from logstats.models import (
    CategoryShare,
    DimensionStatistics,
    LogRecord,
    ParsedUserAgent,
    StatisticalReport,
)
from logstats.parsing import ApacheCombinedLogParser, LogParseError, LogParser
from logstats.pipeline import ReportPipeline
from logstats.reporting import (
    ConsoleReportFormatter,
    CsvReportFormatter,
    JsonReportFormatter,
    ReportFormatter,
    TextReportFormatter,
    build_formatter,
)
from logstats.resolvers import (
    CountryResolver,
    MaxMindCountryResolver,
    UapUserAgentResolver,
    UserAgentResolver,
)
from logstats.service import (
    StatisticsReportService,
    analyze_log_file,
    render_report,
)

__version__ = "1.0.0"

__all__ = [
    "ApacheCombinedLogParser",
    "BrowserDimension",
    "CategoryShare",
    "CountryDimension",
    "CountryResolver",
    "CsvReportFormatter",
    "Dimension",
    "DimensionAggregator",
    "DimensionStatistics",
    "JsonReportFormatter",
    "LogParseError",
    "LogParser",
    "LogRecord",
    "MaxMindCountryResolver",
    "OperatingSystemDimension",
    "ParsedUserAgent",
    "ConsoleReportFormatter",
    "ReportFormatter",
    "ReportPipeline",
    "StatisticalReport",
    "StatisticsReportService",
    "TextReportFormatter",
    "UapUserAgentResolver",
    "UserAgentResolver",
    "analyze_log_file",
    "build_dimensions",
    "build_formatter",
    "render_report",
]
