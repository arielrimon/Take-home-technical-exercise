"""The HTTP Method dimension — buckets a request by its method (GET/POST/...).

Needs no resolver: it reads a field already present on the record. Included to
demonstrate how cheap a brand-new dimension is.
"""

from __future__ import annotations

from logstats.dimensions.base import UNKNOWN_LABEL
from logstats.models import LogRecord


class HttpMethodDimension:
    """Buckets a request by HTTP method (GET/POST/...)."""

    name = "HTTP Method"

    def extract(self, record: LogRecord) -> str:
        """Return the request's HTTP method, or UNKNOWN_LABEL when absent."""
        return record.method or UNKNOWN_LABEL
