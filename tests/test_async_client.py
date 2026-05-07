"""AsyncAtlasClient tests.

One happy path + one error path per live method, plus the parallel
fan-out scenario and deferred NotImplementedError checks.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pandas as pd
import pytest
import respx

from india_energy_atlas import AsyncAtlasClient, PreviewWarning
from india_energy_atlas.client import _PREVIEW_WARNED
from india_energy_atlas.exceptions import AtlasAuthError, AtlasNotFoundError

BASE = "https://api.test.example"


@pytest.fixture
def client() -> AsyncAtlasClient:
    return AsyncAtlasClient(api_key="iea_test_key", base_url=BASE)


@pytest.fixture(autouse=True)
def _clear_preview_warned() -> None:
    _PREVIEW_WARNED.clear()


def _items(data: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, json={"items": data, "count": len(data)})


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


@respx.mock
async def test_health_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "database": {"ok": True}})
    )
    result = await client.health()
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# list_states / get_state
# ---------------------------------------------------------------------------


@respx.mock
async def test_list_states_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/states").mock(
        return_value=_items([{"state_slug": "delhi"}, {"state_slug": "maharashtra"}])
    )
    df = await client.list_states()
    assert isinstance(df, pd.DataFrame)
    assert list(df["state_slug"]) == ["delhi", "maharashtra"]


@respx.mock
async def test_get_state_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/states/delhi").mock(
        return_value=httpx.Response(200, json={"state_slug": "delhi", "counts": {}})
    )
    result = await client.get_state("delhi")
    assert result["state_slug"] == "delhi"


@respx.mock
async def test_get_state_404_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/states/narnia").mock(return_value=httpx.Response(404, json={}))
    with pytest.raises(AtlasNotFoundError):
        await client.get_state("narnia")


# ---------------------------------------------------------------------------
# get_iex_prices
# ---------------------------------------------------------------------------


@respx.mock
async def test_iex_prices_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/iex-market-data").mock(
        return_value=_items(
            [
                {
                    "timestamp": "2026-05-05T00:00:00+00:00",
                    "market_type": "DAM",
                    "region": "N1",
                    "mcp_rs_mwh": "4250.00",
                    "mcv_mw": "10800.000",
                    "purchase_bid_mw": "15721.900",
                    "sell_bid_mw": "12050.500",
                    "source": "iex_api",
                }
            ]
        )
    )
    df = await client.get_iex_prices("DAM")
    assert "mcp_inr_per_mwh" in df.columns
    assert df["mcp_inr_per_mwh"].dtype.kind == "f"


# ---------------------------------------------------------------------------
# get_carbon_intensity
# ---------------------------------------------------------------------------


@respx.mock
async def test_carbon_intensity_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(
        return_value=_items(
            [
                {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "state": "delhi",
                    "carbon_intensity_gco2_kwh": 494.29,
                    "total_generation_mw": 500.0,
                    "confidence": 0.6,
                }
            ]
        )
    )
    with pytest.warns(PreviewWarning):
        df = await client.get_carbon_intensity(state="delhi")
    assert "gco2_per_kwh" in df.columns
    assert df.iloc[0]["gco2_per_kwh"] == pytest.approx(494.29)


async def test_carbon_intensity_discom_raises_async(client: AsyncAtlasClient) -> None:
    with pytest.raises(NotImplementedError, match="IEA-327"):
        await client.get_carbon_intensity(discom="bses-rajdhani")


# ---------------------------------------------------------------------------
# Deferred methods
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "coro",
    [
        pytest.param(
            lambda c: c.get_frequency(start="2025-01-01", end="2025-01-02"),
            id="get_frequency",
        ),
        pytest.param(
            lambda c: c.get_discom_metrics("bses-rajdhani", start="2025-01-01", end="2025-01-02"),
            id="get_discom_metrics",
        ),
        pytest.param(lambda c: c.search_orders(body="cerc", query="x"), id="search_orders"),
        pytest.param(lambda c: c.get_order("x"), id="get_order"),
    ],
)
async def test_async_deferred_raises_not_implemented(client: AsyncAtlasClient, coro: Any) -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        await coro(client)
    assert "IEA-" in str(exc_info.value)


# ---------------------------------------------------------------------------
# get_state_demand — async [IEA-323]
# ---------------------------------------------------------------------------


@respx.mock
async def test_state_demand_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/state-demand").mock(
        return_value=_items(
            [
                {
                    "timestamp": "2025-01-01T05:30:00+05:30",
                    "state": "Delhi",
                    "demand_mw": 4200.5,
                    "source": "metered_sldc",
                    "source_kind": "observed",
                    "confidence": None,
                }
            ]
        )
    )
    df = await client.get_state_demand("delhi", start="2025-01-01", end="2025-01-02")
    assert isinstance(df, pd.DataFrame)
    assert "demand_mw" in df.columns
    assert "provenance" in df.columns
    assert df["demand_mw"].dtype.kind == "f"


# ---------------------------------------------------------------------------
# get_fuel_mix — async [IEA-324]
# ---------------------------------------------------------------------------


@respx.mock
async def test_fuel_mix_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/fuel-mix").mock(
        return_value=_items(
            [
                {
                    "timestamp": "2025-01-01T05:30:00+05:30",
                    "state": "Gujarat",
                    "state_slug": "gujarat",
                    "thermal_mw": 8500.0,
                    "hydro_mw": 350.0,
                    "solar_mw": 0.0,
                    "wind_mw": 600.0,
                    "gas_mw": 1200.0,
                    "nuclear_mw": 0.0,
                    "renewable_mw": 50.0,
                    "total_mw": 10700.0,
                    "source": "canonical_store_v3",
                    "source_kind": "modeled",
                    "confidence": 0.85,
                }
            ]
        )
    )
    df = await client.get_fuel_mix("gujarat", start="2025-01-01", end="2025-01-02")
    assert isinstance(df, pd.DataFrame)
    assert "thermal_mw" in df.columns
    assert "total_mw" in df.columns
    assert df["thermal_mw"].dtype.kind == "f"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


@respx.mock
async def test_auth_error_maps_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/health").mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(AtlasAuthError):
        await client.health()


# ---------------------------------------------------------------------------
# Parallel fan-out with live methods
# ---------------------------------------------------------------------------


@respx.mock
async def test_parallel_carbon_intensity_fan_out(client: AsyncAtlasClient) -> None:
    """Multiple simultaneous carbon-intensity calls via asyncio.gather."""
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(
        return_value=_items(
            [{"timestamp": "2025-01-01T00:00:00+00:00", "carbon_intensity_gco2_kwh": 500.0}]
        )
    )
    states = ["delhi", "maharashtra", "karnataka"]
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PreviewWarning)
        results = await asyncio.gather(*[client.get_carbon_intensity(state=s) for s in states])
    assert len(results) == len(states)
    for df in results:
        assert isinstance(df, pd.DataFrame)


# ---------------------------------------------------------------------------
# list_datasets / get_dataset_metadata / get_dataset — async [IEA-325]
# ---------------------------------------------------------------------------

_CATALOGUE_ITEMS = [
    {"dataset_id": "state_demand", "title": "SLDC State Electricity Demand",
     "endpoint": "/api/intelligence/state-demand", "tier": "free"},
    {"dataset_id": "fuel_mix", "title": "State Hourly Fuel Mix",
     "endpoint": "/api/intelligence/fuel-mix", "tier": "free"},
]

_STATE_DEMAND_META = {
    "dataset_id": "state_demand",
    "endpoint": "/api/intelligence/state-demand",
    "tier": "free",
    "schema": [{"name": "timestamp", "type": "timestamptz"}],
}


@respx.mock
async def test_list_datasets_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/datasets").mock(
        return_value=httpx.Response(200, json={"items": _CATALOGUE_ITEMS, "count": 2})
    )
    df = await client.list_datasets()
    assert isinstance(df, pd.DataFrame)
    assert "dataset_id" in df.columns


@respx.mock
async def test_get_dataset_metadata_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/datasets/state_demand").mock(
        return_value=httpx.Response(200, json=_STATE_DEMAND_META)
    )
    meta = await client.get_dataset_metadata("state_demand")
    assert isinstance(meta, dict)
    assert meta["dataset_id"] == "state_demand"


@respx.mock
async def test_get_dataset_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/api/datasets/state_demand").mock(
        return_value=httpx.Response(200, json=_STATE_DEMAND_META)
    )
    demand_rows = [{"timestamp": "2025-01-01T05:30:00+05:30", "demand_mw": 4200.0}]
    respx.get(f"{BASE}/api/intelligence/state-demand").mock(
        return_value=httpx.Response(200, json={"items": demand_rows, "count": 1})
    )
    df = await client.get_dataset("state_demand", state="delhi")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1


async def test_async_context_manager() -> None:
    async with AsyncAtlasClient(api_key="x", base_url=BASE) as c:
        assert c.api_key == "x"
    with pytest.raises(RuntimeError):
        await c._transport._client.get("/")
