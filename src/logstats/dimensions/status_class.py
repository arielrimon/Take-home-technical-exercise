"""The Status Class dimension — buckets a request by HTTP status class."""

from __future__ import annotations

from logstats.dimensions.base import UNKNOWN_LABEL
from logstats.models import LogRecord


class StatusClassDimension:
    """Buckets a request by HTTP status class (``1xx``..``5xx``)."""

    name = "Status Class"

    def extract(self, record: LogRecord) -> str:
        """Map the numeric status to its ``1xx``..``5xx`` class, else UNKNOWN_LABEL.

        Anything outside the valid HTTP range (absent, or a corrupt code like
        ``0`` or ``700`` that would otherwise yield a nonsensical ``0xx`` / ``7xx``
        bucket) collapses to UNKNOWN_LABEL, so the dimension only ever emits the
        five real status classes plus Unknown.
        """
        if record.status is None or not 100 <= record.status <= 599:
            return UNKNOWN_LABEL
        return f"{record.status // 100}xx"
