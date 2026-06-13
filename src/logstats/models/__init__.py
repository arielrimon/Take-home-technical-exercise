"""Models package — immutable data models shared across the pipeline.

Every value that crosses a component boundary is a Pydantic model rather than a
loose ``dict``: validation at the seams, self-documenting field names, and a
single place to evolve the schema. Each model lives in its own module and is
re-exported here so callers keep importing from ``logstats.models``.
"""

from logstats.models.category_share import CategoryShare
from logstats.models.dimension_statistics import DimensionStatistics
from logstats.models.log_record import LogRecord
from logstats.models.parsed_user_agent import ParsedUserAgent
from logstats.models.partial_aggregate import PartialAggregate
from logstats.models.stage_timings import StageTimings
from logstats.models.statistical_report import StatisticalReport

__all__ = [
    "CategoryShare",
    "DimensionStatistics",
    "LogRecord",
    "ParsedUserAgent",
    "PartialAggregate",
    "StageTimings",
    "StatisticalReport",
]
