"""Gated integration suite — runs only when IEA_API_KEY is set.

Run locally:
    IEA_API_KEY=$KEY pytest tests/integration/ -v

Skips cleanly when IEA_API_KEY is absent. Never required in CI.
"""

from __future__ import annotations

import os
import warnings

import pandas as pd
import pytest

from india_energy_atlas import AtlasClient, PreviewWarning

pytestmark = pytest.mark.skipif(
    not os.environ.get("IEA_API_KEY"),
    reason="IEA_API_KEY not set — skipping live integration tests",
)


@pytest.fixture(scope="module")
def client() -> AtlasClient:
    return AtlasClient()


def test_health_returns_ok(client: AtlasClient) -> None:
    result = client.health()
    assert result["status"] == "ok"
    assert result["database"]["ok"] is True


def test_list_states_nonempty(client: AtlasClient) -> None:
    df = client.list_states()
    assert not df.empty
    assert "state_slug" in df.columns
    assert "state_name" in df.columns
    assert len(df) >= 28


def test_get_state_delhi(client: AtlasClient) -> None:
    result = client.get_state("delhi")
    assert result["state_slug"] == "delhi"
    assert "counts" in result


def test_carbon_intensity_delhi(client: AtlasClient) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PreviewWarning)
        df = client.get_carbon_intensity(state="delhi")
    assert not df.empty
    assert "gco2_per_kwh" in df.columns
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "Asia/Kolkata"
    assert df["gco2_per_kwh"].notna().all()
    assert (df["gco2_per_kwh"] > 0).all()
