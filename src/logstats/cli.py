"""Command-line entry point — a thin front-end over the application service.

This module is intentionally small: it translates command-line arguments into a
single call on :mod:`logstats.service` and writes the result. All wiring of the
parser, resolvers, dimensions and pipeline lives in the service, so the CLI is
just one of potentially many front-ends and duplicates none of that logic.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path

from logstats.dimensions import DEFAULT_DIMENSION_KEYS, DIMENSION_REGISTRY
from logstats.reporting import FORMATTER_REGISTRY
from logstats.service import analyze_log_file, analyze_log_file_parallel, render_report

logger = logging.getLogger(__name__)

# "auto" is a CLI-only meta-format: pretty coloured console output on an
# interactive terminal, plain text when piped / redirected / written to a file.
_AUTO_FORMAT = "auto"
_FORMAT_CHOICES = (_AUTO_FORMAT, *sorted(FORMATTER_REGISTRY))
_COLOR_CHOICES = ("auto", "always", "never")


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the ``argparse`` parser describing the command-line interface."""
    parser = argparse.ArgumentParser(
        prog="logstats",
        description=(
            "Analyse an Apache combined-format access log and report the "
            "percentage breakdown of requests by country, OS and browser."
        ),
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to the Apache access-log file to analyse.",
    )
    parser.add_argument(
        "--geoip-db",
        type=Path,
        required=True,
        help="Path to a MaxMind GeoLite2 Country .mmdb database (used for IP -> country).",
    )
    parser.add_argument(
        "--dimensions",
        default=",".join(DEFAULT_DIMENSION_KEYS),
        help=(
            "Comma-separated dimensions to report. "
            f"Available: {', '.join(sorted(DIMENSION_REGISTRY))}. "
            f"Default: {','.join(DEFAULT_DIMENSION_KEYS)}."
        ),
    )
    parser.add_argument(
        "--format",
        default=_AUTO_FORMAT,
        choices=_FORMAT_CHOICES,
        help=(
            "Output format. 'auto' (default) = a coloured console report on a "
            "terminal, plain 'text' when piped or written to a file."
        ),
    )
    parser.add_argument(
        "--color",
        default="auto",
        choices=_COLOR_CHOICES,
        help="Colourise the console format. 'auto' (default) colours only a real terminal.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Keep only the N most frequent categories per dimension and collapse "
            "the rest into an 'Other' bucket. Default: show every category."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the report to this file instead of stdout.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Number of worker processes to shard the file across for parsing. "
            "1 (default) runs in-process; >1 splits the file into line-aligned "
            "byte ranges and aggregates them in parallel (merged deterministically). "
            "Use 0 to auto-select the CPU count."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging (timing and parse summary) to stderr.",
    )
    return parser


def _parse_dimension_keys(raw: str) -> list[str]:
    """Split, validate and de-duplicate the comma-separated ``--dimensions`` value.

    Returns the cleaned keys with duplicates removed but first-seen order kept;
    raises ``ValueError`` for unknown or empty selections so the caller can
    report the valid choices. De-duplication matters because the aggregator keys
    its per-dimension counters by name: a repeated key (e.g. ``country,country``)
    would otherwise tally the same counter twice per record — doubling its counts
    — and emit the dimension's block twice in the report.
    """
    seen: set[str] = set()
    keys = []
    for key in (token.strip() for token in raw.split(",")):
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    unknown = [key for key in keys if key not in DIMENSION_REGISTRY]
    if unknown:
        valid = ", ".join(sorted(DIMENSION_REGISTRY))
        raise ValueError(f"unknown dimension(s): {', '.join(unknown)}. Valid options: {valid}.")
    if not keys:
        raise ValueError("no dimensions selected.")
    return keys


def _resolve_format_and_color(args: argparse.Namespace) -> tuple[str, bool]:
    """Turn the ``--format`` / ``--color`` / ``--output`` flags into concrete settings.

    The output sink is "interactive" only when writing to stdout *and* stdout is
    a TTY; that drives both the 'auto' format (console vs. text) and 'auto'
    colour (on vs. off), so piping to a file always yields plain, parseable text.
    """
    sink_is_tty = args.output is None and sys.stdout.isatty()
    format_name = args.format
    if format_name == _AUTO_FORMAT:
        format_name = "console" if sink_is_tty else "text"
    use_color = {"always": True, "never": False, "auto": sink_is_tty}[args.color]
    return format_name, use_color


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI: parse args, call the service, render and emit the report.

    Returns a process exit code (``0`` on success, ``2`` on a usage / input
    error such as a missing file, unknown dimension or non-positive ``--top-n``).
    """
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    # Validate inputs up front and fail with actionable messages.
    try:
        dimension_keys = _parse_dimension_keys(args.dimensions)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.top_n is not None and args.top_n < 1:
        # A non-positive top-n is meaningless (and Python's negative slicing
        # would otherwise collapse the *largest* categories instead). Reject it.
        print("error: --top-n must be a positive integer.", file=sys.stderr)
        return 2
    if args.workers < 0:
        # 0 means "auto (CPU count)" and 1 means "in-process"; negative is invalid.
        print("error: --workers must be 0 (auto) or a positive integer.", file=sys.stderr)
        return 2
    if not args.log_file.is_file():
        print(f"error: log file not found: {args.log_file}", file=sys.stderr)
        return 2
    if not args.geoip_db.is_file():
        print(
            f"error: GeoIP database not found: {args.geoip_db}\n"
            "Download a MaxMind GeoLite2 Country database (see README) and pass it via --geoip-db.",
            file=sys.stderr,
        )
        return 2

    # All wiring and I/O happens inside the service; the CLI just asks for the
    # report and renders it. `--workers 1` is the in-process path; anything else
    # (a count, or 0 for "auto") shards the file across worker processes.
    if args.workers == 1:
        report = analyze_log_file(
            args.log_file,
            args.geoip_db,
            dimensions=dimension_keys,
            top_n=args.top_n,
        )
    else:
        report = analyze_log_file_parallel(
            args.log_file,
            args.geoip_db,
            dimensions=dimension_keys,
            top_n=args.top_n,
            workers=None if args.workers == 0 else args.workers,
        )

    format_name, use_color = _resolve_format_and_color(args)
    rendered = render_report(report, format_name, color=use_color)

    # Write to the chosen sink (file or stdout). ``nullcontext`` lets the same
    # ``with`` block handle "stdout" (which must not be closed) and a real file.
    output_context = args.output.open("w", encoding="utf-8") if args.output else nullcontext(sys.stdout)
    with output_context as sink:
        print(rendered, file=sink)
    if args.output:
        print(f"report written to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
