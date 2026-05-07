"""Tests for live typed methods: health, list_states, get_state, get_iex_prices."""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd
import pytest
import respx

from india_energy_atlas import AtlasClient

BASE = "https://api.test.example"


@pytest.fixture
def client() -> AtlasClient:
    return AtlasClient(api_key="iea_test_key", base_url=BASE)


def _items(data: list[dict[str, Any]], **extra: Any) -> httpx.Response:
    body: dict[str, Any] = {"items": data, "count": len(data)}
    body.update(extra)
    return httpx.Response(200, json=body)


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


@respx.mock
def test_health_returns_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/health").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "checked_at": "2026-05-07T06:00:00+00:00",
                "database": {"ok": True},
                "workspace": {"root": "/app"},
            },
        )
    )
    result = client.health()
    assert result["status"] == "ok"
    assert result["database"]["ok"] is True


@respx.mock
def test_health_typeguard_on_non_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/health").mock(return_value=httpx.Response(200, json=["a"]))
    with pytest.raises(TypeError):
        client.health()


# ---------------------------------------------------------------------------
# list_states
# ---------------------------------------------------------------------------


@respx.mock
def test_list_states_returns_dataframe(client: AtlasClient) -> None:
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
                    "counts": {},
                },
                {
                    "state_slug": "maharashtra",
                    "state_name": "MAHARASHTRA",
                    "iso_code": "IN-MH",
                    "build_status": "unknown",
                    "release_tier": "tier-1",
                    "completion_class": "partial",
                    "counts": {},
                },
            ]
        )
    )
    df = client.list_states()
    assert isinstance(df, pd.DataFrame)
    assert list(df["state_slug"]) == ["delhi", "maharashtra"]
    assert "release_tier" in df.columns


@respx.mock
def test_list_states_empty(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/states").mock(return_value=_items([]))
    df = client.list_states()
    assert df.empty


# ---------------------------------------------------------------------------
# get_state
# ---------------------------------------------------------------------------


@respx.mock
def test_get_state_returns_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/states/delhi").mock(
        return_value=httpx.Response(
            200,
            json={
                "state_slug": "delhi",
                "state_name": "DELHI",
                "iso_code": "IN-DE",
                "counts": {"canonical_edges": 481, "canonical_nodes": 68},
                "geometry": {"type": "MultiPolygon"},
            },
        )
    )
    result = client.get_state("delhi")
    assert result["state_slug"] == "delhi"
    assert result["counts"]["canonical_nodes"] == 68


@respx.mock
def test_get_state_typeguard_on_non_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/states/x").mock(return_value=httpx.Response(200, json=["a"]))
    with pytest.raises(TypeError):
        client.get_state("x")


# ---------------------------------------------------------------------------
# get_iex_prices
# ---------------------------------------------------------------------------

IEX_ROWS = [
    {
        "timestamp": "2026-05-05T00:00:00+00:00",
        "market_type": "DAM",
        "region": "N1",
        "purchase_bid_mw": "15721.900",
        "sell_bid_mw": "12050.500",
        "mcv_mw": "10800.000",
        "mcp_rs_mwh": "4250.00",
        "source": "iex_api",
    },
    {
        "timestamp": "2026-05-05T01:00:00+00:00",
        "market_type": "DAM",
        "region": "N1",
        "purchase_bid_mw": "14900.000",
        "sell_bid_mw": "11200.300",
        "mcv_mw": "10200.000",
        "mcp_rs_mwh": "3980.00",
        "source": "iex_api",
    },
]


@respx.mock
def test_iex_prices_returns_dataframe_with_renamed_column(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/iex-market-data").mock(return_value=_items(IEX_ROWS))
    df = client.get_iex_prices("DAM")
    assert isinstance(df, pd.DataFrame)
    assert "mcp_inr_per_mwh" in df.columns
    assert "mcp_rs_mwh" not in df.columns


@respx.mock
def test_iex_prices_numeric_coercion(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/iex-market-data").mock(return_value=_items(IEX_ROWS))
    df = client.get_iex_prices("DAM")
    assert df["mcp_inr_per_mwh"].dtype.kind == "f"
    assert df["purchase_bid_mw"].dtype.kind == "f"
    assert df["mcv_mw"].dtype.kind == "f"
    # values coerce cleanly (no NaN from the captured payload)
    assert df["mcp_inr_per_mwh"].notna().all()


@respx.mock
def test_iex_prices_passes_market_type_uppercase(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/iex-market-data").mock(return_value=_items([]))
    client.get_iex_prices("RTM")
    qs = dict(route.calls.last.request.url.params)
    assert qs["market_type"] == "RTM"


@respx.mock
def test_iex_prices_tz_aware_index(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/iex-market-data").mock(return_value=_items(IEX_ROWS))
    df = client.get_iex_prices("DAM")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "Asia/Kolkata"


@respx.mock
def test_iex_prices_client_side_start_filter(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/iex-market-data").mock(return_value=_items(IEX_ROWS))
    # start after first row → only second row should survive
    df = client.get_iex_prices("DAM", start="2026-05-05T01:00:00+00:00")
    assert len(df) == 1


@respx.mock
def test_iex_prices_empty(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/iex-market-data").mock(return_value=_items([]))
    df = client.get_iex_prices("DAM")
    assert df.empty
