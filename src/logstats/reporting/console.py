"""Console formatter — colourful, aligned tables with inline bar charts.

Built for interactive terminals (via the ``rich`` library); degrades to clean
monochrome tables when colour is disabled (e.g. piped to a file).
"""

from __future__ import annotations

import io
import shutil

from rich.box import SIMPLE_HEAVY
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from logstats.aggregation import DEFAULT_OTHER_LABEL, UNKNOWN_LABEL
from logstats.models import DimensionStatistics, StatisticalReport
from logstats.reporting.base import PERCENT_DECIMALS

# Eighth-block characters give the inline bar chart sub-character resolution, so
# a 4.23% slice still renders a visible sliver rather than nothing.
_BAR_EIGHTHS = " ▏▎▍▌▋▊▉█"
_BAR_WIDTH = 22
# Palette cycled across dimensions so each metric block is visually distinct.
_DIMENSION_COLORS = ("green", "magenta", "cyan", "yellow", "blue", "red")
# Residual / unresolved categories are drawn in muted grey to set them apart.
_MUTED_CATEGORIES = frozenset({UNKNOWN_LABEL, DEFAULT_OTHER_LABEL})


class ConsoleReportFormatter:
    """Renders the report as colourful, aligned tables with inline bar charts.

    Each dimension becomes a table whose rows are sorted by frequency, with a
    unicode bar scaled to that dimension's largest share so the shape of the
    distribution is obvious at a glance. Colour is opt-in (``color``) so the very
    same formatter degrades to clean monochrome tables when piped or redirected.
    """

    def __init__(self, color: bool = True, width: int | None = None) -> None:
        """Configure colour output and an optional fixed render width.

        ``width`` defaults to the detected terminal width (falling back to 100
        columns) so the tables fill the available space without wrapping.
        """
        self._color = color
        self._width = width

    def format(self, report: StatisticalReport) -> str:
        """Render the whole report to a string of (optionally coloured) tables."""
        width = self._width or shutil.get_terminal_size((100, 40)).columns
        buffer = io.StringIO()
        # ``force_terminal`` makes Rich emit styling even though we write to an
        # in-memory buffer; ``color_system=None`` disables it for the mono path.
        console = Console(
            file=buffer,
            force_terminal=self._color,
            color_system="standard" if self._color else None,
            width=width,
            highlight=False,
            emoji=False,
        )
        self._render_header(console, report)
        for index, dimension in enumerate(report.dimensions):
            # Separate consecutive dimension tables with a blank line so each
            # metric block reads as a distinct section (the header already
            # supplies the spacing before the first table).
            if index:
                console.print()
            console.print(self._render_dimension(dimension, index))
        return buffer.getvalue().rstrip("\n")

    @staticmethod
    def _render_header(console: Console, report: StatisticalReport) -> None:
        """Print a title rule plus a one-line analysed/skipped summary."""
        skipped = (
            f" · [yellow]{report.skipped_lines:,} skipped[/]" if report.skipped_lines else ""
        )
        # ``escape`` the source: it is a user-supplied path and must not be
        # interpreted as Rich markup (an embedded ``[...]`` would otherwise be
        # swallowed as a style tag, or a stray ``[/]`` would raise MarkupError).
        console.rule(f"[bold]Log report[/] · {escape(report.source)}")
        console.print(f"[dim]{report.parsed_records:,} requests analysed{skipped}[/]\n")

    def _render_dimension(self, dimension: DimensionStatistics, index: int) -> Table:
        """Build the Rich table for one dimension, bars scaled to its top share."""
        accent = _DIMENSION_COLORS[index % len(_DIMENSION_COLORS)]
        table = Table(
            # ``escape`` the dimension name for the same reason as category
            # values below: it may originate from an extension dimension and is
            # data, not markup.
            title=f"[bold {accent}]{escape(dimension.name)}[/]",
            title_justify="left",
            box=SIMPLE_HEAVY,
            show_edge=False,
            pad_edge=False,
            expand=False,
        )
        table.add_column("Category", no_wrap=True)
        table.add_column("Distribution")
        table.add_column("Share", justify="right")
        table.add_column("Count", justify="right", style="dim")

        if not dimension.shares:
            table.add_row("[dim](no data)[/]", "", "", "")
            return table

        # Scale every bar relative to the largest share so the top row's bar is
        # full-width and the rest are proportional to it.
        max_percentage = max(share.percentage for share in dimension.shares)
        for share in dimension.shares:
            table.add_row(
                self._category_text(share.value),
                self._bar_markup(share.percentage, max_percentage, share.value, accent),
                f"[bold]{share.percentage:.{PERCENT_DECIMALS}f}%[/]",
                f"{share.count:,}",
            )
        return table

    @staticmethod
    def _category_text(value: str) -> str:
        """Style the category label, muting the Unknown / Other buckets.

        Category values are external data (country names, and — for extension
        dimensions such as path/referer — fully attacker-controlled request
        fields), so they are ``escape``d before being placed into markup. Without
        this, a value containing ``[...]`` would be reinterpreted as a style tag
        and a value of ``[/]`` would raise a ``MarkupError`` and abort the render.
        """
        safe_value = escape(value)
        if value == UNKNOWN_LABEL:
            return f"[yellow]{safe_value}[/]"
        if value == DEFAULT_OTHER_LABEL:
            return f"[bright_black]{safe_value}[/]"
        return safe_value

    @staticmethod
    def _bar_markup(percentage: float, max_percentage: float, value: str, accent: str) -> str:
        """Return Rich markup for a proportional unicode bar for one row."""
        if max_percentage <= 0:
            return ""
        eighths = round((percentage / max_percentage) * _BAR_WIDTH * 8)
        bar = "█" * (eighths // 8)
        if eighths % 8:
            bar += _BAR_EIGHTHS[eighths % 8]
        color = "bright_black" if value in _MUTED_CATEGORIES else accent
        return f"[{color}]{bar}[/]"
