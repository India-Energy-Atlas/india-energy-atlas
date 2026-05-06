"""`iea` command-line interface.

Wired in pyproject.toml as a console script. Provides a quick way to
list datasets, fetch one, see metadata, and report the version.

Output format for `iea fetch` is selected by the file extension:
  .csv      -> pandas to_csv
  .parquet  -> pandas to_parquet (requires pyarrow, in deps)
  .json     -> pandas to_json (orient=records, lines=True)
  .jsonl    -> same as .json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from india_energy_atlas import AtlasClient, __version__

app = typer.Typer(
    name="iea",
    help="India Energy Atlas SDK command-line interface.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()

SUPPORTED_SUFFIXES = (".csv", ".parquet", ".json", ".jsonl")


def _make_client(api_key: str | None, base_url: str | None) -> AtlasClient:
    if base_url:
        return AtlasClient(api_key=api_key, base_url=base_url)
    return AtlasClient(api_key=api_key)


# typer requires Option() at default position; B008 is intentionally suppressed
# at the call sites below.


@app.command(name="version")
def cmd_version() -> None:
    """Print the SDK version."""
    typer.echo(f"india-energy-atlas {__version__}")


@app.command(name="datasets")
def cmd_datasets(
    api_key: str | None = typer.Option(None, "--api-key", envvar="IEA_API_KEY"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="IEA_BASE_URL"),
) -> None:
    """List available datasets in a pretty table."""
    client = _make_client(api_key, base_url)
    try:
        df = client.list_datasets()
    finally:
        client.close()

    if df.empty:
        console.print("[yellow]No datasets returned.[/yellow]")
        return

    table = Table(title="India Energy Atlas — Datasets", show_lines=False)
    for col in df.columns:
        table.add_column(str(col))
    for _, row in df.iterrows():
        table.add_row(*(str(v) for v in row.tolist()))
    console.print(table)


@app.command(name="metadata")
def cmd_metadata(
    dataset: str = typer.Argument(..., help="Dataset id (e.g. sldc_demand)."),
    api_key: str | None = typer.Option(None, "--api-key", envvar="IEA_API_KEY"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="IEA_BASE_URL"),
) -> None:
    """Print schema/units/source/provenance/refresh cadence for one dataset."""
    client = _make_client(api_key, base_url)
    try:
        meta: dict[str, Any] = client.get_dataset_metadata(dataset)
    finally:
        client.close()
    typer.echo(json.dumps(meta, indent=2, sort_keys=True, default=str))


@app.command(name="fetch")
def cmd_fetch(
    dataset: str = typer.Argument(..., help="Dataset id (e.g. sldc_demand)."),
    out: Path = typer.Option(  # noqa: B008
        ...,
        "--out",
        "-o",
        help="Output file path. Format inferred from suffix: .csv | .parquet | .json | .jsonl.",
    ),
    start: str | None = typer.Option(None, "--start", help="ISO date / timestamp."),
    end: str | None = typer.Option(None, "--end", help="ISO date / timestamp."),
    columns: str | None = typer.Option(None, "--columns", help="Comma-separated column whitelist."),
    limit: int | None = typer.Option(None, "--limit", help="Max rows."),
    filter_column: str | None = typer.Option(None, "--filter-column"),
    filter_operator: str | None = typer.Option(None, "--filter-operator"),
    filter_value: str | None = typer.Option(None, "--filter-value"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="IEA_API_KEY"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="IEA_BASE_URL"),
) -> None:
    """Fetch one dataset to CSV / Parquet / JSONL."""
    suffix = out.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        typer.echo(
            f"Unsupported output suffix {suffix!r}. Use one of {SUPPORTED_SUFFIXES}.",
            err=True,
        )
        sys.exit(2)

    client = _make_client(api_key, base_url)
    try:
        col_list = [c.strip() for c in columns.split(",")] if columns else None
        df = client.get_dataset(
            dataset,
            start=start,
            end=end,
            columns=col_list,
            filter_column=filter_column,
            filter_operator=filter_operator,  # type: ignore[arg-type]
            filter_value=filter_value,
            limit=limit,
        )
    finally:
        client.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".csv":
        df.to_csv(out)
    elif suffix == ".parquet":
        df.to_parquet(out)
    else:  # .json or .jsonl
        df.to_json(out, orient="records", lines=True, date_format="iso")
    typer.echo(f"wrote {len(df):,} rows -> {out}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
