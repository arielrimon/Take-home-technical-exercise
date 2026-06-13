"""The :class:`CategoryShare` model — one row of a dimension breakdown."""

from __future__ import annotations

from pydantic import BaseModel


class CategoryShare(BaseModel):
    """A single row in a dimension breakdown: one category and its share.

    For example ``value="United States", count=3908, percentage=39.08`` means
    39.08% of the analysed requests originated from the United States.
    """

    value: str
    """The category label (a country, OS family, browser family, ...)."""

    count: int
    """Number of requests that fell into this category."""

    percentage: float
    """Share of the dimension total, in percent, rounded to two decimals.

    Rounded by the aggregator with the largest-remainder method so a dimension's
    percentages sum to exactly 100.00; formatters render this value directly.
    """
