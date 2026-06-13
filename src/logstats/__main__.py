"""Enables ``python -m logstats ...`` by delegating to the CLI entry point."""

from logstats.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
