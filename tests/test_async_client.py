"""AsyncAtlasClient tests (IEA-317).

One happy path + one error path per method, plus the parallel
fan-out scenario the AC spec calls out.
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
from india_energy_atlas.exceptions import (
    AtlasAuthError,
    AtlasNotFoundError,
    AtlasValidationError,
)

BASE = "https://api.test.example/v1"


@pytest.fixture
def client() -> AsyncAtlasClient:
    return AsyncAtlasClient(api_key="iea_test_key", base_url=BASE)


@pytest.fixture(autouse=True)
def _clear_preview_warned() -> None:
    _PREVIEW_WARNED.clear()


def _page(data: list[dict[str, Any]], next_cursor: str | None = None) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "next_cursor": next_cursor})


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@respx.mock
async def test_list_datasets(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/datasets").mock(
        return_value=_page([{"dataset_id": "sldc_demand"}, {"dataset_id": "iex"}])
    )
    df = await client.list_datasets()
    assert list(df["dataset_id"]) == ["sldc_demand", "iex"]


@respx.mock
async def test_get_dataset_metadata(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/datasets/x").mock(
        return_value=httpx.Response(200, json={"dataset_id": "x", "units": {}})
    )
    meta = await client.get_dataset_metadata("x")
    assert meta["dataset_id"] == "x"


@respx.mock
async def test_get_dataset(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/datasets/x/rows").mock(
        return_value=_page([{"timestamp": "2025-01-01T00:00:00Z", "v": 1}])
    )
    df = await client.get_dataset("x", start="2025-01-01", end="2025-01-02")
    assert df.iloc[0]["v"] == 1


# ---------------------------------------------------------------------------
# Typed methods
# ---------------------------------------------------------------------------


@respx.mock
async def test_state_demand_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/sldc/demand").mock(
        return_value=_page(
            [{"timestamp": "2025-01-01T00:00:00Z", "state": "delhi", "demand_mw": 4200.0}]
        )
    )
    df = await client.get_state_demand(["delhi"], start="2025-01-01", end="2025-01-02")
    assert df.iloc[0]["demand_mw"] == 4200.0


async def test_state_demand_validation_async(client: AsyncAtlasClient) -> None:
    with pytest.raises(ValueError, match="Unknown state slug"):
        await client.get_state_demand(["narnia"], start="2025-01-01", end="2025-01-02")


@respx.mock
async def test_fuel_mix_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/sldc/fuel-mix").mock(
        return_value=_page([{"timestamp": "2025-01-01T00:00:00Z", "coal_mw": 8500}])
    )
    df = await client.get_fuel_mix("gujarat", start="2025-01-01", end="2025-01-02")
    assert df.iloc[0]["coal_mw"] == 8500


@respx.mock
async def test_iex_prices_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/iex/clearing-prices").mock(
        return_value=_page([{"timestamp": "2025-01-01T00:00:00Z", "mcp_inr_per_mwh": 4250.0}])
    )
    df = await client.get_iex_prices("dam", start="2025-01-01", end="2025-01-02")
    assert df.iloc[0]["mcp_inr_per_mwh"] == 4250.0


async def test_iex_prices_validation_async(client: AsyncAtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="market"):
        await client.get_iex_prices(
            "monthly",  # type: ignore[arg-type]
            start="2025-01-01",
            end="2025-01-02",
        )


@respx.mock
async def test_carbon_intensity_async_emits_preview(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/carbon/intensity").mock(
        return_value=_page([{"timestamp": "2025-06-01T00:00:00Z", "gco2_per_kwh": 690.0}])
    )
    with pytest.warns(PreviewWarning):
        df = await client.get_carbon_intensity(
            discom="bses-rajdhani", start="2025-06-01", end="2025-06-02"
        )
    assert df.iloc[0]["gco2_per_kwh"] == 690.0


@respx.mock
async def test_discom_metrics_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/discom/metrics").mock(
        return_value=_page([{"timestamp": "2025-01-01T00:00:00Z", "atc_loss": 0.12}])
    )
    df = await client.get_discom_metrics("bses-rajdhani", start="2025-01-01", end="2025-12-31")
    assert df.iloc[0]["atc_loss"] == 0.12


@respx.mock
async def test_frequency_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/grid/frequency").mock(
        return_value=_page(
            [{"timestamp": "2025-01-01T00:00:00Z", "frequency_hz": 49.99, "region": "NR"}]
        )
    )
    df = await client.get_frequency(start="2025-01-01", end="2025-01-02")
    assert df.iloc[0]["frequency_hz"] == 49.99


# ---------------------------------------------------------------------------
# Regulatory
# ---------------------------------------------------------------------------


@respx.mock
async def test_search_orders_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/regulatory/orders").mock(
        return_value=_page([{"order_id": "cerc/2024/178/2024-08-12", "issued_at": "2024-08-12"}])
    )
    df = await client.search_orders(body="cerc", query="green tariff")
    assert df.iloc[0]["order_id"] == "cerc/2024/178/2024-08-12"


@respx.mock
async def test_get_order_404_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/regulatory/orders/x").mock(return_value=httpx.Response(404, json={}))
    with pytest.raises(AtlasNotFoundError):
        await client.get_order("x")


# ---------------------------------------------------------------------------
# Error mapping + parallel fan-out (the AC's headline scenario)
# ---------------------------------------------------------------------------


@respx.mock
async def test_auth_error_maps_async(client: AsyncAtlasClient) -> None:
    respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(AtlasAuthError):
        await client.list_datasets()


@respx.mock
async def test_parallel_fan_out_works(client: AsyncAtlasClient) -> None:
    """asyncio.gather(*[get_state_demand(state=s, ...)]) per the AC."""
    respx.get(f"{BASE}/sldc/demand").mock(
        return_value=_page([{"timestamp": "2025-01-01T00:00:00Z", "demand_mw": 1000}])
    )
    states = ["delhi", "maharashtra", "tamil-nadu", "punjab", "karnataka"]
    results = await asyncio.gather(
        *[client.get_state_demand([s], start="2025-01-01", end="2025-01-02") for s in states]
    )
    assert len(results) == len(states)
    for df in results:
        assert isinstance(df, pd.DataFrame)
        assert df.iloc[0]["demand_mw"] == 1000


async def test_async_context_manager() -> None:
    async with AsyncAtlasClient(api_key="x", base_url=BASE) as c:
        assert c.api_key == "x"
    # After exit, the underlying client is closed; another call raises.
    with pytest.raises(RuntimeError):
        await c._transport._client.get("/")
