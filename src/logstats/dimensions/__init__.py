"""Dimensions package — the pluggable "what category does this request fall into?".

A :class:`Dimension` maps a :class:`LogRecord` to a single category label. This
is the primary extension point of the module: **adding a new statistic is just
adding a new Dimension file and registering it** — no parser, aggregator, or
formatter change is required.

Layout (one dimension per module):

* :mod:`logstats.dimensions.base`             — ``Dimension`` protocol, ``UNKNOWN_LABEL``, normalisation
* :mod:`logstats.dimensions.country`          — ``CountryDimension``
* :mod:`logstats.dimensions.operating_system` — ``OperatingSystemDimension``
* :mod:`logstats.dimensions.browser`          — ``BrowserDimension``
* :mod:`logstats.dimensions.http_method`      — ``HttpMethodDimension``
* :mod:`logstats.dimensions.status_class`     — ``StatusClassDimension``
* :mod:`logstats.dimensions.registry`         — name → factory registry + ``build_dimensions``
"""

from logstats.dimensions.base import UNKNOWN_LABEL, Dimension, normalise_unknown
from logstats.dimensions.browser import BrowserDimension
from logstats.dimensions.country import CountryDimension
from logstats.dimensions.http_method import HttpMethodDimension
from logstats.dimensions.operating_system import OperatingSystemDimension
from logstats.dimensions.registry import (
    DEFAULT_DIMENSION_KEYS,
    DIMENSION_REGISTRY,
    DimensionFactory,
    build_dimensions,
)
from logstats.dimensions.status_class import StatusClassDimension

__all__ = [
    "DEFAULT_DIMENSION_KEYS",
    "DIMENSION_REGISTRY",
    "UNKNOWN_LABEL",
    "BrowserDimension",
    "CountryDimension",
    "Dimension",
    "DimensionFactory",
    "HttpMethodDimension",
    "OperatingSystemDimension",
    "StatusClassDimension",
    "build_dimensions",
    "normalise_unknown",
]
