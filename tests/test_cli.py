"""Typer CLI tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import respx
from typer.testing import CliRunner

from india_energy_atlas import __version__
from india_energy_atlas.cli import app

BASE = "https://api.test.example"
runner = CliRunner()


def _items(data: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, json={"items": data, "count": len(data)})


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("health", "states", "datasets", "fetch", "version"):
        assert cmd in result.stdout


def test_version_prints_sdk_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


@respx.mock
def test_health_prints_json() -> None:
    respx.get(f"{BASE}/api/health").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "database": {"ok": True}, "workspace": {}}
        )
    )
    result = runner.invoke(app, ["health", "--api-key", "iea_test", "--base-url", BASE])
    assert result.exit_code == 0
    assert '"status"' in result.stdout
    assert "ok" in result.stdout


@respx.mock
def test_states_renders_table() -> None:
    respx.get(f"{BASE}/api/states").mock(
        return_value=_items(
            [
                {
                    "state_slug": "delhi",
                    "state_name": "DELHI",
                    "iso_code": "IN-DE",
                    "build_status": "unknown",
                    "release_tier": "tier-3",
                    "completion_class": "osm-only",
                },
            ]
        )
    )
    result = runner.invoke(app, ["states", "--api-key", "iea_test", "--base-url", BASE])
    assert result.exit_code == 0
    assert "delhi" in result.stdout


def test_datasets_exits_nonzero() -> None:
    result = runner.invoke(app, ["datasets", "--api-key", "iea_test", "--base-url", BASE])
    assert result.exit_code != 0
    assert "IEA-325" in result.stdout


@respx.mock
def test_fetch_carbon_intensity_writes_csv(tmp_path: Path) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(
        return_value=_items(
            [
                {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "state": "delhi",
                    "carbon_intensity_gco2_kwh": 494.29,
                    "total_generation_mw": 500.0,
                    "confidence": 0.6,
                },
                {
                    "timestamp": "2025-01-01T01:00:00+00:00",
                    "state": "delhi",
                    "carbon_intensity_gco2_kwh": 518.37,
                    "total_generation_mw": 360.0,
                    "confidence": 0.6,
                },
            ]
        )
    )
    out = tmp_path / "delhi.csv"
    result = runner.invoke(
        app,
        [
            "fetch",
            "carbon-intensity",
            "--state",
            "delhi",
            "--out",
            str(out),
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
    assert "gco2_per_kwh" in df.columns


def test_fetch_unsupported_suffix_errors(tmp_path: Path) -> None:
    out = tmp_path / "x.xlsx"
    result = runner.invoke(
        app,
        [
            "fetch",
            "carbon-intensity",
            "--state",
            "delhi",
            "--out",
            str(out),
            "--api-key",
            "iea_test",
            "--base-url",
            BASE,
        ],
    )
    assert result.exit_code == 2


def test_fetch_carbon_intensity_missing_state_errors(tmp_path: Path) -> None:
    out = tmp_path / "x.csv"
    result = runner.invoke(
        app,
        [
            "fetch",
            "carbon-intensity",
            "--out",
            str(out),
            "--api-key",
            "iea_test",
            "--base-url",
            BASE,
        ],
    )
    assert result.exit_code != 0


def test_fetch_unknown_dataset_errors(tmp_path: Path) -> None:
    out = tmp_path / "x.csv"
    result = runner.invoke(
        app,
        [
            "fetch",
            "sldc_demand",
            "--out",
            str(out),
            "--api-key",
            "iea_test",
            "--base-url",
            BASE,
        ],
    )
    assert result.exit_code != 0
