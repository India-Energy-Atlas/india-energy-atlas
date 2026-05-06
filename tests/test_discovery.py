"""Discovery method tests.

Covers AtlasClient.list_datasets, get_dataset_metadata, and the generic
get_dataset escape hatch. Uses respx to mock the Atlas API surface.
"""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd
import pytest
import respx

from india_energy_atlas import AtlasClient

BASE = "https://api.test.example/v1"


@pytest.fixture
def client() -> AtlasClient:
    return AtlasClient(api_key="iea_test_key", base_url=BASE)


def _page(data: list[dict[str, Any]], next_cursor: str | None) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "next_cursor": next_cursor})


@respx.mock
def test_list_datasets_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/datasets").mock(
        return_value=_page(
            [
                {
                    "dataset_id": "sldc_demand",
                    "title": "State load dispatch demand",
                    "granularity": "hourly",
                    "coverage_start": "2022-01-01",
                    "coverage_end": "2026-05-06",
                    "tier": "production",
                },
                {
                    "dataset_id": "iex_clearing_prices",
                    "title": "IEX clearing prices",
                    "granularity": "15min",
                    "coverage_start": "2022-01-01",
                    "coverage_end": "2026-05-06",
                    "tier": "production",
                },
            ],
            next_cursor=None,
        )
    )
    df = client.list_datasets()
    assert isinstance(df, pd.DataFrame)
    assert list(df["dataset_id"]) == ["sldc_demand", "iex_clearing_prices"]
    assert "granularity" in df.columns
    assert "tier" in df.columns


@respx.mock
def test_list_datasets_paginates(client: AtlasClient) -> None:
    pages = iter(
        [
            _page([{"dataset_id": "a"}, {"dataset_id": "b"}], next_cursor="c1"),
            _page([{"dataset_id": "c"}], next_cursor=None),
        ]
    )
    respx.get(f"{BASE}/datasets").mock(side_effect=lambda req: next(pages))
    df = client.list_datasets()
    assert list(df["dataset_id"]) == ["a", "b", "c"]


@respx.mock
def test_get_dataset_metadata_returns_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/datasets/sldc_demand").mock(
        return_value=httpx.Response(
            200,
            json={
                "dataset_id": "sldc_demand",
                "schema": [
                    {"name": "timestamp", "type": "timestamptz"},
                    {"name": "state", "type": "string"},
                    {"name": "demand_mw", "type": "double"},
                ],
                "units": {"demand_mw": "MW"},
                "source": "SLDC publications",
                "provenance": "observed",
                "refresh_cadence": "hourly",
            },
        )
    )
    meta = client.get_dataset_metadata("sldc_demand")
    assert meta["dataset_id"] == "sldc_demand"
    assert meta["units"]["demand_mw"] == "MW"
    assert meta["refresh_cadence"] == "hourly"


@respx.mock
def test_get_dataset_metadata_typeguard_on_non_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/datasets/x").mock(return_value=httpx.Response(200, json=[1, 2, 3]))
    with pytest.raises(TypeError):
        client.get_dataset_metadata("x")


@respx.mock
def test_get_dataset_returns_tz_aware_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/datasets/sldc_demand/rows").mock(
        return_value=_page(
            [
                {"timestamp": "2025-01-01T00:00:00+00:00", "state": "delhi", "demand_mw": 4200.0},
                {"timestamp": "2025-01-01T01:00:00+00:00", "state": "delhi", "demand_mw": 4100.5},
            ],
            next_cursor=None,
        )
    )
    df = client.get_dataset(
        "sldc_demand",
        start="2025-01-01",
        end="2025-01-02",
    )
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "Asia/Kolkata"
    # First row: 00:00 UTC == 05:30 IST
    assert df.index[0].hour == 5 and df.index[0].minute == 30


@respx.mock
def test_get_dataset_passes_filters_and_window(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/datasets/sldc_demand/rows").mock(
        return_value=_page([], next_cursor=None)
    )
    client.get_dataset(
        "sldc_demand",
        start="2025-01-01",
        end="2025-01-31",
        columns=["timestamp", "state", "demand_mw"],
        filter_column="state",
        filter_operator="in",
        filter_value=["delhi", "punjab"],
        limit=500,
    )
    sent = route.calls.last.request
    qs = dict(sent.url.params)
    assert qs["start"] == "2025-01-01"
    assert qs["end"] == "2025-01-31"
    assert qs["columns"] == "timestamp,state,demand_mw"
    assert qs["filter_column"] == "state"
    assert qs["filter_operator"] == "in"
    assert qs["filter_value"] == "delhi,punjab"


@respx.mock
def test_get_dataset_partial_filter_raises(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="all be set together"):
        client.get_dataset("sldc_demand", filter_column="state")


@respx.mock
def test_get_dataset_pagination_with_limit(client: AtlasClient) -> None:
    pages = iter(
        [
            _page(
                [{"timestamp": "2025-01-01T00:00:00Z", "v": i} for i in range(3)],
                next_cursor="p2",
            ),
            _page(
                [{"timestamp": "2025-01-01T03:00:00Z", "v": i} for i in range(3, 6)],
                next_cursor=None,
            ),
        ]
    )
    respx.get(f"{BASE}/datasets/x/rows").mock(side_effect=lambda req: next(pages))
    df = client.get_dataset("x", limit=4)
    assert len(df) == 4
    assert list(df["v"]) == [0, 1, 2, 3]


@respx.mock
def test_get_dataset_handles_timestamp_input(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/datasets/x/rows").mock(return_value=_page([], next_cursor=None))
    client.get_dataset(
        "x",
        start=pd.Timestamp("2025-01-01T00:00:00", tz="UTC"),
        end=pd.Timestamp("2025-01-02T00:00:00", tz="UTC"),
    )
    qs = dict(route.calls.last.request.url.params)
    assert qs["start"].startswith("2025-01-01")
    assert qs["end"].startswith("2025-01-02")
