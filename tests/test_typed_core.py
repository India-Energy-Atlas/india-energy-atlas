"""Tests for the typed core methods (IEA-314).

get_state_demand, get_fuel_mix, get_iex_prices.
"""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd
import pytest
import respx

from india_energy_atlas import AtlasClient
from india_energy_atlas.exceptions import AtlasValidationError

BASE = "https://api.test.example/v1"


@pytest.fixture
def client() -> AtlasClient:
    return AtlasClient(api_key="iea_test_key", base_url=BASE)


def _page(data: list[dict[str, Any]], next_cursor: str | None = None) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "next_cursor": next_cursor})


# ---------------------------------------------------------------------------
# get_state_demand
# ---------------------------------------------------------------------------


@respx.mock
def test_state_demand_returns_tz_aware_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/sldc/demand").mock(
        return_value=_page(
            [
                {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "state": "delhi",
                    "demand_mw": 4200.0,
                    "provenance": "observed",
                },
                {
                    "timestamp": "2025-01-01T01:00:00+00:00",
                    "state": "delhi",
                    "demand_mw": 4150.5,
                    "provenance": "modeled",
                },
            ]
        )
    )
    df = client.get_state_demand(["delhi"], start="2025-01-01", end="2025-01-02")
    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "Asia/Kolkata"
    assert "provenance" in df.columns
    assert set(df["provenance"]) == {"observed", "modeled"}


@respx.mock
def test_state_demand_accepts_string_state(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/sldc/demand").mock(return_value=_page([]))
    client.get_state_demand("delhi", start="2025-01-01", end="2025-01-02")
    qs = dict(route.calls.last.request.url.params)
    assert qs["states"] == "delhi"


@respx.mock
def test_state_demand_csv_joins_multiple_states(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/sldc/demand").mock(return_value=_page([]))
    client.get_state_demand(
        ["delhi", "maharashtra", "tamil-nadu"],
        start="2025-01-01",
        end="2025-01-02",
    )
    qs = dict(route.calls.last.request.url.params)
    assert qs["states"] == "delhi,maharashtra,tamil-nadu"


def test_state_demand_rejects_unknown_state(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="Unknown state slug"):
        client.get_state_demand(["narnia"], start="2025-01-01", end="2025-01-02")


def test_state_demand_rejects_bad_granularity(client: AtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="granularity"):
        client.get_state_demand(
            ["delhi"],
            start="2025-01-01",
            end="2025-01-02",
            granularity="weekly",  # type: ignore[arg-type]
        )


def test_state_demand_rejects_inverted_window(client: AtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="end"):
        client.get_state_demand(
            ["delhi"],
            start="2025-02-01",
            end="2025-01-01",
        )


# ---------------------------------------------------------------------------
# get_fuel_mix
# ---------------------------------------------------------------------------


@respx.mock
def test_fuel_mix_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/sldc/fuel-mix").mock(
        return_value=_page(
            [
                {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "state": "gujarat",
                    "coal_mw": 8500.0,
                    "gas_mw": 1200.0,
                    "hydro_mw": 350.0,
                    "solar_mw": 0.0,
                    "wind_mw": 600.0,
                    "nuclear_mw": 0.0,
                    "other_mw": 100.0,
                    "provenance": "observed",
                },
            ]
        )
    )
    df = client.get_fuel_mix("gujarat", start="2025-01-01", end="2025-01-07")
    assert "coal_mw" in df.columns
    assert "wind_mw" in df.columns
    assert df.iloc[0]["coal_mw"] == 8500.0


def test_fuel_mix_rejects_unknown_state(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="Unknown state slug"):
        client.get_fuel_mix("atlantis", start="2025-01-01", end="2025-01-02")


# ---------------------------------------------------------------------------
# get_iex_prices
# ---------------------------------------------------------------------------


@respx.mock
def test_iex_prices_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/iex/clearing-prices").mock(
        return_value=_page(
            [
                {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "mcp_inr_per_mwh": 4250.0,
                    "mcv_mw": 5500.0,
                    "cleared_mw": 5400.0,
                    "area": "N1",
                },
            ]
        )
    )
    df = client.get_iex_prices("dam", start="2025-01-01", end="2025-01-02")
    assert "mcp_inr_per_mwh" in df.columns
    assert df.iloc[0]["mcp_inr_per_mwh"] == 4250.0


def test_iex_prices_rejects_unknown_market(client: AtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="market"):
        client.get_iex_prices("monthly", start="2025-01-01", end="2025-01-02")  # type: ignore[arg-type]


@respx.mock
def test_iex_prices_passes_market_param(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/iex/clearing-prices").mock(return_value=_page([]))
    client.get_iex_prices("rtm", start="2025-01-01", end="2025-01-02")
    qs = dict(route.calls.last.request.url.params)
    assert qs["market"] == "rtm"
