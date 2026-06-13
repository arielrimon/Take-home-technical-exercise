# logstats — Apache access-log statistical reporting

Reads an Apache **combined**-format access log and reports the percentage
breakdown of requests by **Country**, **OS**, and **Browser** (and any other
dimension you register). Built for extensibility — see [`DESIGN.md`](./DESIGN.md)
for the architecture and the reasoning behind it.

```
Country:
United States 39.08%
France 8.65%
...

OS:
Windows 33.15%
Unknown 24.49%
...

Browser:
Chrome 28.92%
Firefox 26.07%
...
```

## Requirements

- Python **3.11+**
- A MaxMind **GeoLite2 Country** database (`.mmdb`) for IP → country lookup
- The Apache log file to analyse

## Setup

Using [`uv`](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync                      # creates .venv and installs deps from pyproject.toml
```

Or with plain `pip`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .             # installs geoip2, user-agents, pydantic
```

### Get the data

1. **Apache log** (10k lines):
   ```bash
   mkdir -p data
   curl -sL "https://www.dropbox.com/s/xs47xk59p7mgkbz/apache_log.txt?dl=1" -o data/apache_log.txt
   ```
2. **GeoLite2 Country database** — the assignment requires the *downloadable*
   database (not the rate-limited web API). Sign up for a free MaxMind account
   at <https://www.maxmind.com/en/geolite2/signup>, download **GeoLite2-Country**,
   and place `GeoLite2-Country.mmdb` in `data/`.

> The log and the `.mmdb` are intentionally **git-ignored** (size + MaxMind
> licence). Fetch them locally as above.

## Usage

```bash
# Default: Country / OS / Browser. On a terminal you get a coloured table report
# with inline bar charts; piped/redirected it falls back to plain text.
python -m logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb

# Collapse each dimension's long tail into an "Other" bucket.
python -m logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb --top-n 5

# Pick an explicit format (auto | console | text | json | csv).
python -m logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb --format console
python -m logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb --format json
python -m logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb --format csv

# Choose / add dimensions (status & method ship as built-in extras).
python -m logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb --dimensions country,os,browser,status,method

# Write to a file, and show timing/parse summary on stderr.
python -m logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb --output report.txt --verbose
```

If installed (`pip install -e .` / `uv sync`), a `logstats` console script is
also available, e.g. `logstats data/apache_log.txt --geoip-db data/GeoLite2-Country.mmdb`.

### Options

| Flag | Description | Default |
|---|---|---|
| `log_file` | Path to the Apache access log (positional) | — |
| `--geoip-db PATH` | Path to the GeoLite2 Country `.mmdb` | **required** |
| `--dimensions a,b,c` | Which dimensions to report. Available: `country`, `os`, `browser`, `status`, `method` | `country,os,browser` |
| `--format {auto,console,text,json,csv}` | Output format. `auto` = `console` on a terminal, `text` when piped/written to a file | `auto` |
| `--color {auto,always,never}` | Colourise the `console` format (`auto` colours only a real terminal) | `auto` |
| `--top-n N` | Keep the N most frequent categories per dimension; collapse the rest into `Other` | show all |
| `--output PATH` | Write the report to a file instead of stdout | stdout |
| `--verbose` | Log timing and parse summary to stderr | off |

## Output semantics

- Each metric is reported **separately**, **sorted by frequency descending**,
  with **two decimal places** (per the requirements).
- `Unknown` = a value that could not be resolved (IP missing from the DB, or an
  unrecognised User-Agent). It is a real category and sorts by its own frequency.
- `Other` = the collapsed long tail of small known categories (only when
  `--top-n` is used); always shown last.
- Percentages are computed over **successfully parsed** records; malformed lines
  are skipped and counted (visible via `--verbose` or the `json` format).

## Use as a library (building other front-ends)

The CLI is just one thin front-end. All wiring lives in
`logstats.service`, so any other entry point — an HTTP API, a notebook, a
scheduled job — reuses the same composition root.

```python
from logstats.service import analyze_log_file, render_report

# One-shot: open the GeoIP DB + log file, analyse, clean up.
report = analyze_log_file("access.log", "GeoLite2-Country.mmdb",
                          dimensions=["country", "os", "browser"], top_n=5)

report.model_dump()                 # JSON-ready dict — ideal for a web response
print(render_report(report, "text"))  # or render to text/console/json/csv
```

```python
from logstats.service import StatisticsReportService

# Long-running service: build once (GeoIP DB opened once, resolver caches
# shared), then serve many requests.
service = StatisticsReportService.from_geoip_path("GeoLite2-Country.mmdb")
with open("access.log") as stream:
    report = service.generate(stream, source="access.log", dimensions=["country"])
```

Custom geo source or log format? Inject your own `CountryResolver` /
`UserAgentResolver` / `LogParser` into `StatisticsReportService` — nothing else
changes.

## Development

```bash
# Run the test suite (no GeoIP DB or network needed — resolvers are faked).
PYTHONPATH=src python -m pytest
# or, after `uv sync` / `pip install -e .[dev]`:
pytest
```

### Design document

The Phase-1 design lives in [`DESIGN.md`](./DESIGN.md) (renders with diagrams on
GitHub). [`DATAFLOW.md`](./DATAFLOW.md) traces the full runtime data flow and the
classes/components at each step.

## Project layout

Each multi-class concern is a small package with one class/concept per file.

```
src/logstats/
  parsing.py            LogParser + ApacheCombinedLogParser     (raw line → LogRecord)
  models/               LogRecord, ParsedUserAgent, CategoryShare, DimensionStatistics, StatisticalReport
  resolvers/            base protocols + MaxMind country + UA resolver   (enrichment + caching)
  dimensions/           Dimension protocol + one file per dimension + registry   ← add dimensions here
  aggregation/          DimensionAggregator                     (streaming counts → stats)
  reporting/            ReportFormatter + text/console/json/csv + registry        ← add formats here
  pipeline.py           ReportPipeline                          (wires parsing + aggregation)
  service/              StatisticsReportService, analyze_log_file, render_report  ← reuse from any front-end
  cli.py                argparse front-end over the service     (one of many possible entry points)
tests/                  unit + integration + end-to-end tests (fakes for unit; real data for integration/e2e)
DESIGN.md               Phase 1 design document (Markdown, renders on GitHub)
```
