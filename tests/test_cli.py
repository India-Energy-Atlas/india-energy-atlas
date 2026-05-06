"""Typer CLI tests (IEA-318)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import respx
from typer.testing import CliRunner

from india_energy_atlas import __version__
from india_energy_atlas.cli import app

BASE = "https://api.test.example/v1"
runner = CliRunner()


def _page(data: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "next_cursor": None})


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    for cmd in ("datasets", "metadata", "fetch", "version"):
        assert cmd in out


def test_version_prints_sdk_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


@respx.mock
def test_datasets_renders_table() -> None:
    respx.get(f"{BASE}/datasets").mock(
        return_value=_page([{"dataset_id": "sldc_demand", "title": "SLDC demand"}])
    )
    result = runner.invoke(app, ["datasets", "--api-key", "iea_test", "--base-url", BASE])
    assert result.exit_code == 0
    assert "sldc_demand" in result.stdout


@respx.mock
def test_metadata_outputs_json() -> None:
    respx.get(f"{BASE}/datasets/sldc_demand").mock(
        return_value=httpx.Response(
            200, json={"dataset_id": "sldc_demand", "units": {"demand_mw": "MW"}}
        )
    )
    result = runner.invoke(
        app,
        ["metadata", "sldc_demand", "--api-key", "iea_test", "--base-url", BASE],
    )
    assert result.exit_code == 0
    assert '"dataset_id"' in result.stdout
    assert "sldc_demand" in result.stdout


@respx.mock
def test_fetch_writes_csv(tmp_path: Path) -> None:
    respx.get(f"{BASE}/datasets/sldc_demand/rows").mock(
        return_value=_page(
            [
                {"timestamp": "2025-01-01T00:00:00Z", "state": "delhi", "demand_mw": 4200.0},
                {"timestamp": "2025-01-01T01:00:00Z", "state": "delhi", "demand_mw": 4150.5},
            ]
        )
    )
    out = tmp_path / "x.csv"
    result = runner.invoke(
        app,
        [
            "fetch",
            "sldc_demand",
            "--out",
            str(out),
            "--start",
            "2025-01-01",
            "--end",
            "2025-01-02",
            "--api-key",
            "iea_test",
            "--base-url",
            BASE,
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    df = pd.read_csv(out)
    assert len(df) == 2
    assert "demand_mw" in df.columns


@respx.mock
def test_fetch_writes_parquet(tmp_path: Path) -> None:
    respx.get(f"{BASE}/datasets/x/rows").mock(
        return_value=_page([{"timestamp": "2025-01-01T00:00:00Z", "v": 1}])
    )
    out = tmp_path / "x.parquet"
    result = runner.invoke(
        app,
        ["fetch", "x", "--out", str(out), "--api-key", "iea_test", "--base-url", BASE],
    )
    assert result.exit_code == 0, result.stdout
    df = pd.read_parquet(out)
    assert len(df) == 1
    assert df.iloc[0]["v"] == 1


@respx.mock
def test_fetch_writes_jsonl(tmp_path: Path) -> None:
    respx.get(f"{BASE}/datasets/x/rows").mock(
        return_value=_page(
            [
                {"timestamp": "2025-01-01T00:00:00Z", "v": 1},
                {"timestamp": "2025-01-01T01:00:00Z", "v": 2},
            ]
        )
    )
    out = tmp_path / "x.jsonl"
    result = runner.invoke(
        app,
        ["fetch", "x", "--out", str(out), "--api-key", "iea_test", "--base-url", BASE],
    )
    assert result.exit_code == 0, result.stdout
    lines = out.read_text().strip().split("\n")
    assert len(lines) == 2


def test_fetch_unsupported_suffix_errors(tmp_path: Path) -> None:
    out = tmp_path / "x.xlsx"
    result = runner.invoke(
        app,
        ["fetch", "sldc_demand", "--out", str(out), "--api-key", "iea_test", "--base-url", BASE],
    )
    assert result.exit_code == 2
    assert "Unsupported output suffix" in result.stderr or "Unsupported" in result.stdout
