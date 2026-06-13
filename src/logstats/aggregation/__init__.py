"""Aggregation package — count category frequencies per dimension in one pass.

Exposes :class:`DimensionAggregator` and the ``Other`` / ``Unknown`` labels so
report builders can reference the same constants the aggregator and dimensions use.
"""

from logstats.aggregation.aggregator import DEFAULT_OTHER_LABEL, DimensionAggregator
from logstats.dimensions import UNKNOWN_LABEL

__all__ = ["DEFAULT_OTHER_LABEL", "UNKNOWN_LABEL", "DimensionAggregator"]
