"""The :class:`Dimension` protocol plus the shared "unknown" normalisation.

A *dimension* maps a :class:`LogRecord` to a single category label. This module
holds the interface every dimension satisfies and the small helper that
normalises missing / unrecognised values to one consistent label, so the
concrete dimensions in sibling modules stay focused on their own extraction.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from logstats.models import LogRecord

# Single label for "we could not determine a value" across every dimension, so
# the report is consistent. Distinct from the aggregator's "Other" bucket, which
# collapses the long tail of *known* small categories.
UNKNOWN_LABEL = "Unknown"

# Values that the underlying libraries emit to mean "not recognised". They are
# normalised to UNKNOWN_LABEL so unresolved records read consistently.
_UNRECOGNISED_VALUES = frozenset({"", "Other"})


def normalise_unknown(value: str | None) -> str:
    """Collapse missing / "not recognised" values to the shared UNKNOWN_LABEL."""
    if value is None or value in _UNRECOGNISED_VALUES:
        return UNKNOWN_LABEL
    return value


@runtime_checkable
class Dimension(Protocol):
    """A named rule mapping a record to one category label.

    ``name`` is the heading shown in the report (e.g. ``Country``); ``extract``
    returns the category this record belongs to for that dimension.
    """

    name: str

    def extract(self, record: LogRecord) -> str:
        """Return the category label this ``record`` falls into for the dimension."""
        ...
