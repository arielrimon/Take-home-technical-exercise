"""End-to-end tests driving the CLI exactly as a user would.

Error paths need no external data and always run. Success paths analyse the real
dataset and are skipped when it is absent. One test crosses a real process
boundary via ``python -m logstats`` to prove the packaged entry point works.
"""

from __future__ import annotations

import json
import subprocess
import sys

from logstats.cli import _parse_dimension_keys, main

from .conftest import APACHE_LOG_PATH, GEOIP_DB_PATH, requires_dataset

# A minimal but valid combined-format line for tests that need a real log file
# without depending on the full dataset.
_ONE_LINE = (
    '8.8.8.8 - - [17/May/2015:10:05:03 +0000] "GET / HTTP/1.1" 200 1 "-" '
    '"Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/32.0 Safari/537.36"\n'
)


# --------------------------- error / usage paths ----------------------------


def test_missing_log_file_returns_2(capsys) -> None:
    code = main(["/no/such/file.log", "--geoip-db", str(GEOIP_DB_PATH)])
    assert code == 2
    assert "log file not found" in capsys.readouterr().err


def test_missing_geoip_db_returns_2(tmp_path, capsys) -> None:
    log_file = tmp_path / "access.log"
    log_file.write_text(_ONE_LINE, encoding="utf-8")
    code = main([str(log_file), "--geoip-db", str(tmp_path / "missing.mmdb")])
    assert code == 2
    assert "GeoIP database not found" in capsys.readouterr().err


def test_unknown_dimension_returns_2(capsys) -> None:
    code = main(["x.log", "--geoip-db", "y.mmdb", "--dimensions", "country,bogus"])
    assert code == 2
    assert "unknown dimension" in capsys.readouterr().err


def test_empty_dimensions_returns_2(capsys) -> None:
    code = main(["x.log", "--geoip-db", "y.mmdb", "--dimensions", " , "])
    assert code == 2
    assert "no dimensions selected" in capsys.readouterr().err


def test_non_positive_top_n_returns_2(capsys) -> None:
    code = main(["x.log", "--geoip-db", "y.mmdb", "--top-n", "0"])
    assert code == 2
    assert "--top-n must be a positive integer" in capsys.readouterr().err


def test_duplicate_dimension_keys_are_deduplicated() -> None:
    # Repeated keys must collapse to one (first-seen order preserved); otherwise
    # the aggregator would tally the shared per-name counter twice and emit the
    # dimension's block twice with doubled counts.
    assert _parse_dimension_keys("country,country,os,country") == ["country", "os"]


# ------------------------------ success paths -------------------------------


@requires_dataset
def test_text_output_to_stdout(capsys) -> None:
    code = main(
        [str(APACHE_LOG_PATH), "--geoip-db", str(GEOIP_DB_PATH), "--format", "text",
         "--dimensions", "country,os,browser"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Country:" in out and "OS:" in out and "Browser:" in out
    # Two-decimal percentage formatting is present.
    assert "%" in out
    assert "United States" in out


@requires_dataset
def test_json_output_is_parseable(capsys) -> None:
    code = main(
        [str(APACHE_LOG_PATH), "--geoip-db", str(GEOIP_DB_PATH), "--format", "json",
         "--dimensions", "os"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_lines"] == 10_000
    assert payload["parsed_records"] == 9_999
    assert payload["skipped_lines"] == 1
    assert payload["dimensions"][0]["name"] == "OS"


@requires_dataset
def test_writes_report_to_file(tmp_path, capsys) -> None:
    out_file = tmp_path / "report.txt"
    code = main(
        [str(APACHE_LOG_PATH), "--geoip-db", str(GEOIP_DB_PATH), "--dimensions", "browser",
         "--output", str(out_file)]
    )
    assert code == 0
    assert out_file.is_file()
    contents = out_file.read_text(encoding="utf-8")
    assert "Browser:" in contents
    assert "report written to" in capsys.readouterr().err


@requires_dataset
def test_subprocess_module_entrypoint() -> None:
    """True process-boundary e2e: `python -m logstats ... --format json`."""
    result = subprocess.run(
        [sys.executable, "-m", "logstats", str(APACHE_LOG_PATH),
         "--geoip-db", str(GEOIP_DB_PATH), "--format", "json", "--dimensions", "country"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dimensions"][0]["name"] == "Country"
    assert payload["parsed_records"] == 9_999
