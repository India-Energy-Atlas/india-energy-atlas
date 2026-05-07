"""`iea` command-line interface.

Wired in pyproject.toml as a console script. Provides quick access to
live endpoints: health, states, and carbon-intensity fetch.

Output format for `iea fetch` is selected by the file extension:
  .csv      -> pandas to_csv
  .parquet  -> pandas to_parquet (requires pyarrow, in deps)
  .json     -> pandas to_json (orient=records, lines=True)
  .jsonl    -> same as .json
"""

from __future__ import annotations

import sys
from pathlib import Path

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


@app.command(name="version")
def cmd_version() -> None:
    """Print the SDK version."""
    typer.echo(f"india-energy-atlas {__version__}")


@app.command(name="health")
def cmd_health(
    api_key: str | None = typer.Option(None, "--api-key", envvar="IEA_API_KEY"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="IEA_BASE_URL"),
) -> None:
    """Check API health status."""
    client = _make_client(api_key, base_url)
    try:
        result = client.health()
    finally:
        client.close()
    import json

    typer.echo(json.dumps(result, indent=2, default=str))


@app.command(name="states")
def cmd_states(
    api_key: str | None = typer.Option(None, "--api-key", envvar="IEA_API_KEY"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="IEA_BASE_URL"),
) -> None:
    """List available states in a pretty table."""
    client = _make_client(api_key, base_url)
    try:
        df = client.list_states()
    finally:
        client.close()

    if df.empty:
        console.print("[yellow]No states returned.[/yellow]")
        return

    show_cols = [
        c
        for c in [
            "state_slug",
            "state_name",
            "iso_code",
            "release_tier",
            "build_status",
            "completion_class",
        ]
        if c in df.columns
    ]
    table = Table(title="India Energy Atlas — States", show_lines=False)
    for col in show_cols:
        table.add_column(col)
    for _, row in df[show_cols].iterrows():
        table.add_row(*(str(v) for v in row.tolist()))
    console.print(table)


@app.command(name="datasets")
def cmd_datasets(
    api_key: str | None = typer.Option(None, "--api-key", envvar="IEA_API_KEY"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="IEA_BASE_URL"),
) -> None:
    """List available datasets. (Not yet live — landing in IEA-325.)"""
    console.print(
        "[yellow]The /api/datasets endpoint is not yet live.[/yellow]\n"
        "It lands in IEA-325: https://linear.app/sayon/issue/IEA-325\n"
        "Use [bold]iea states[/bold] to list states, or [bold]iea fetch carbon-intensity[/bold] for data."
    )
    raise typer.Exit(code=1)


@app.command(name="fetch")
def cmd_fetch(
    dataset: str = typer.Argument(
        ...,
        help="Dataset to fetch. Supported: carbon-intensity",
    ),
    out: Path = typer.Option(  # noqa: B008
        ...,
        "--out",
        "-o",
        help="Output file path. Format inferred from suffix: .csv | .parquet | .json | .jsonl.",
    ),
    state: str | None = typer.Option(None, "--state", help="State slug (e.g. delhi)."),
    start: str | None = typer.Option(None, "--start", help="ISO date / timestamp."),
    end: str | None = typer.Option(None, "--end", help="ISO date / timestamp."),
    api_key: str | None = typer.Option(None, "--api-key", envvar="IEA_API_KEY"),
    base_url: str | None = typer.Option(None, "--base-url", envvar="IEA_BASE_URL"),
) -> None:
    """Fetch a dataset to CSV / Parquet / JSONL.

    Supported datasets: carbon-intensity
    """
    suffix = out.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        typer.echo(
            f"Unsupported output suffix {suffix!r}. Use one of {SUPPORTED_SUFFIXES}.",
            err=True,
        )
        sys.exit(2)

    client = _make_client(api_key, base_url)
    try:
        if dataset == "carbon-intensity":
            if not state:
                typer.echo("--state is required for carbon-intensity", err=True)
                sys.exit(2)
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = client.get_carbon_intensity(state=state, start=start, end=end)
        else:
            typer.echo(
                f"Dataset {dataset!r} not yet supported. Try: carbon-intensity",
                err=True,
            )
            sys.exit(2)
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
