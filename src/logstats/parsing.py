"""Log-line parsing: raw text in, structured :class:`LogRecord` out.

The :class:`LogParser` protocol is the extension point for supporting other log
layouts (nginx, JSON access logs, ...). The only concrete implementation today
is :class:`ApacheCombinedLogParser`, which understands the Apache "combined"
log format that this assignment targets.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from logstats.models import LogRecord


class LogParseError(ValueError):
    """Raised when a line does not conform to the parser's expected format.

    The pipeline catches this per-line so a single malformed entry (for example
    a truncated record) is skipped and counted rather than aborting the run.
    """


@runtime_checkable
class LogParser(Protocol):
    """Strategy that turns a single raw log line into a :class:`LogRecord`.

    Implementations must raise :class:`LogParseError` for lines they cannot
    parse so the pipeline can account for them as skipped.
    """

    def parse(self, line: str) -> LogRecord:
        """Parse ``line`` into a :class:`LogRecord` or raise :class:`LogParseError`."""
        ...


class ApacheCombinedLogParser:
    """Parses the Apache "combined" access-log format with one anchored regex.

    The combined format is::

        %h %l %u [%t] "%r" %>s %b "%{Referer}i" "%{User-Agent}i"

    i.e. host, ident, user, time, request line, status, response size, referer
    and user-agent. The quoted fields are matched with an escape-aware pattern
    (``(?:[^"\\\\]|\\\\.)*``) so an embedded ``\\"`` does not prematurely close
    the field. The request line (``"%r"``) is split a second time into method,
    path and protocol because those are useful as independent dimensions.
    """

    # One regex for the whole line. Anchored at both ends (``match`` + ``$``) so
    # structurally broken lines — such as a record with an unterminated quoted
    # user-agent — fail fast and are reported as malformed instead of being
    # silently half-parsed.
    _LINE_PATTERN = re.compile(
        r'(?P<ip>\S+)\s+'
        r'(?P<identity>\S+)\s+'
        r'(?P<user>\S+)\s+'
        r'\[(?P<timestamp>[^\]]+)\]\s+'
        r'"(?P<request>(?:[^"\\]|\\.)*)"\s+'
        r'(?P<status>\d+|-)\s+'
        r'(?P<size>\d+|-)\s+'
        r'"(?P<referer>(?:[^"\\]|\\.)*)"\s+'
        r'"(?P<user_agent>(?:[^"\\]|\\.)*)"\s*$'
    )

    def parse(self, line: str) -> LogRecord:
        """Decompose a combined-format line into a fully typed :class:`LogRecord`.

        Raises :class:`LogParseError` when the line does not match the format.
        Individual soft fields (status, size) degrade to ``None`` rather than
        failing the whole line, because a request is still useful for
        country/OS/browser statistics even if, say, its size is absent. The
        timestamp is carried as its raw string and parsed lazily by the record
        (see :attr:`LogRecord.timestamp`), keeping ``strptime`` off the hot path.

        The record is built with :meth:`~pydantic.BaseModel.model_construct`,
        which skips Pydantic validation: the regex above has already proven the
        field shapes, so re-validating every one of millions of records per run
        is redundant work — model_construct is the documented fast path for
        trusted, already-validated data.
        """
        match = self._LINE_PATTERN.match(line.rstrip("\n"))
        if match is None:
            raise LogParseError(f"line does not match Apache combined format: {line[:120]!r}")

        method, path, protocol = self._split_request_line(match.group("request"))
        return LogRecord.model_construct(
            ip=match.group("ip"),
            identity=match.group("identity"),
            user=match.group("user"),
            timestamp_raw=match.group("timestamp"),
            method=method,
            path=path,
            protocol=protocol,
            status=self._parse_int(match.group("status")),
            size=self._parse_int(match.group("size")),
            referer=match.group("referer"),
            user_agent=match.group("user_agent"),
        )

    @staticmethod
    def _split_request_line(request: str) -> tuple[str, str, str]:
        """Split a request line such as ``GET /index.html HTTP/1.1`` into parts.

        Returns ``(method, path, protocol)``. Malformed or empty request lines
        (e.g. ``-``) degrade gracefully: whatever is present is placed into the
        path and the missing tokens come back as empty strings, so the record
        is still usable for non-request dimensions.
        """
        tokens = request.split(" ")
        if len(tokens) >= 3:
            # Path may itself contain spaces in pathological cases, so treat the
            # first token as the method, the last as the protocol, and rejoin
            # everything in between as the path.
            return tokens[0], " ".join(tokens[1:-1]), tokens[-1]
        if len(tokens) == 2:
            return tokens[0], tokens[1], ""
        return "", request, ""

    @staticmethod
    def _parse_int(raw: str) -> int | None:
        """Convert a numeric log field to ``int``; treat ``-`` / non-numeric as ``None``."""
        return int(raw) if raw.isdigit() else None
