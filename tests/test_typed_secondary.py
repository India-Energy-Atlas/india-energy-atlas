"""Tests for get_carbon_intensity and all deferred (NotImplementedError) methods."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pandas as pd
import pytest
import respx

from india_energy_atlas import AtlasClient, PreviewWarning
from india_energy_atlas.client import _PREVIEW_WARNED

BASE = "https://api.test.example"


@pytest.fixture
def client() -> AtlasClient:
    return AtlasClient(api_key="iea_test_key", base_url=BASE)


@pytest.fixture(autouse=True)
def _clear_preview_warned() -> None:
    _PREVIEW_WARNED.clear()


@contextmanager
def warnings_caught() -> Iterator[list[warnings.WarningMessage]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield caught


def _items(data: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, json={"items": data, "count": len(data)})


CARBON_ROWS = [
    {
        "timestamp": "2025-01-01T00:00:00+00:00",
        "state": "delhi",
        "state_slug": "delhi",
        "carbon_intensity_gco2_kwh": 494.29,
        "intensity_class": "yellow",
        "total_generation_mw": 500.802,
        "dominant_fuel": "thermal",
        "source": "derived_aggregate",
        "confidence": 0.6,
        "emission_factors_version": "cea_co2_baseline_v18",
        "scope_key": "delhi",
        "emission_factors_basis": "lifecycle",
    },
    {
        "timestamp": "2025-01-01T01:00:00+00:00",
        "state": "delhi",
        "state_slug": "delhi",
        "carbon_intensity_gco2_kwh": 518.37,
        "intensity_class": "yellow",
        "total_generation_mw": 360.42,
        "dominant_fuel": "thermal",
        "source": "derived_aggregate",
        "confidence": 0.6,
        "emission_factors_version": "cea_co2_baseline_v18",
        "scope_key": "delhi",
        "emission_factors_basis": "lifecycle",
    },
]


# ---------------------------------------------------------------------------
# get_carbon_intensity — live endpoint
# ---------------------------------------------------------------------------


@respx.mock
def test_carbon_intensity_returns_renamed_column(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(return_value=_items(CARBON_ROWS))
    with pytest.warns(PreviewWarning):
        df = client.get_carbon_intensity(state="delhi")
    assert isinstance(df, pd.DataFrame)
    assert "gco2_per_kwh" in df.columns
    assert "carbon_intensity_gco2_kwh" not in df.columns


@respx.mock
def test_carbon_intensity_numeric_coercion(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(return_value=_items(CARBON_ROWS))
    with pytest.warns(PreviewWarning):
        df = client.get_carbon_intensity(state="delhi")
    assert df["gco2_per_kwh"].dtype.kind == "f"
    assert df["total_generation_mw"].dtype.kind == "f"
    assert df["gco2_per_kwh"].notna().all()


@respx.mock
def test_carbon_intensity_tz_aware_index(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(return_value=_items(CARBON_ROWS))
    with pytest.warns(PreviewWarning):
        df = client.get_carbon_intensity(state="delhi")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "Asia/Kolkata"


@respx.mock
def test_carbon_intensity_passes_state_param(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(return_value=_items([]))
    with pytest.warns(PreviewWarning):
        client.get_carbon_intensity(state="maharashtra")
    qs = dict(route.calls.last.request.url.params)
    assert qs["state"] == "maharashtra"


@respx.mock
def test_carbon_intensity_preview_warning_once(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(return_value=_items([]))
    with pytest.warns(PreviewWarning):
        client.get_carbon_intensity(state="delhi")
    # second call: no warning
    with warnings_caught() as caught:
        client.get_carbon_intensity(state="delhi")
    assert not any(isinstance(w.message, PreviewWarning) for w in caught)


def test_carbon_intensity_discom_raises_not_implemented(client: AtlasClient) -> None:
    with pytest.raises(NotImplementedError, match="IEA-327"):
        client.get_carbon_intensity(discom="bses-rajdhani")


def test_carbon_intensity_no_state_raises(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="state="):
        client.get_carbon_intensity()


@respx.mock
def test_carbon_intensity_client_side_start_filter(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(return_value=_items(CARBON_ROWS))
    with pytest.warns(PreviewWarning):
        df = client.get_carbon_intensity(state="delhi", start="2025-01-01T01:00:00+00:00")
    assert len(df) == 1


# ---------------------------------------------------------------------------
# Deferred methods — all must raise NotImplementedError with tracking issue
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.list_datasets(), id="list_datasets"),
        pytest.param(lambda c: c.get_dataset_metadata("x"), id="get_dataset_metadata"),
        pytest.param(lambda c: c.get_dataset("x"), id="get_dataset"),
        pytest.param(
            lambda c: c.get_frequency(start="2025-01-01", end="2025-01-02"),
            id="get_frequency",
        ),
        pytest.param(
            lambda c: c.get_discom_metrics("bses-rajdhani", start="2025-01-01", end="2025-01-02"),
            id="get_discom_metrics",
        ),
        pytest.param(lambda c: c.search_orders(body="cerc", query="x"), id="search_orders"),
        pytest.param(lambda c: c.get_order("cerc/2024/1/2024-01-01"), id="get_order"),
    ],
)
def test_deferred_method_raises_not_implemented(client: AtlasClient, call: Any) -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        call(client)
    msg = str(exc_info.value)
    # Must mention the tracking issue
    assert "IEA-" in msg


@pytest.mark.parametrize(
    "call,ticket",
    [
        (lambda c: c.list_datasets(), "IEA-325"),
        (lambda c: c.get_dataset_metadata("x"), "IEA-325"),
        (lambda c: c.get_dataset("x"), "IEA-325"),
        (lambda c: c.get_frequency(start="2025-01-01", end="2025-01-02"), "IEA-326"),
        (
            lambda c: c.get_discom_metrics("bses-rajdhani", start="2025-01-01", end="2025-01-02"),
            "IEA-327",
        ),
        (lambda c: c.search_orders(body="cerc", query="x"), "IEA-328"),
        (lambda c: c.get_order("cerc/2024/1/2024-01-01"), "IEA-328"),
    ],
)
def test_deferred_method_names_correct_ticket(client: AtlasClient, call: Any, ticket: str) -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        call(client)
    assert ticket in str(exc_info.value)


# ---------------------------------------------------------------------------
# get_state_demand — live [IEA-323]
# ---------------------------------------------------------------------------

_DEMAND_ROWS = [
    {
        "timestamp": "2025-01-01T05:30:00+05:30",
        "state": "Delhi",
        "demand_mw": 4200.5,
        "source": "metered_sldc",
        "source_kind": "observed",
        "confidence": None,
    },
    {
        "timestamp": "2025-01-01T06:30:00+05:30",
        "state": "Delhi",
        "demand_mw": 4350.0,
        "source": "modeled_v2",
        "source_kind": "modeled",
        "confidence": 0.85,
    },
]


@respx.mock
def test_state_demand_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/state-demand").mock(
        return_value=_items(_DEMAND_ROWS)
    )
    df = client.get_state_demand("delhi", start="2025-01-01", end="2025-01-02")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "demand_mw" in df.columns


@respx.mock
def test_state_demand_renames_source_kind_to_provenance(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/state-demand").mock(
        return_value=_items(_DEMAND_ROWS)
    )
    df = client.get_state_demand("delhi", start="2025-01-01", end="2025-01-02")
    assert "provenance" in df.columns
    assert "source_kind" not in df.columns


@respx.mock
def test_state_demand_numeric_coercion(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/state-demand").mock(
        return_value=_items(_DEMAND_ROWS)
    )
    df = client.get_state_demand("delhi", start="2025-01-01", end="2025-01-02")
    assert df["demand_mw"].dtype.kind == "f"


@respx.mock
def test_state_demand_passes_params(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/state-demand").mock(
        return_value=_items([])
    )
    client.get_state_demand(
        ["delhi", "maharashtra"],
        start="2025-01-01",
        end="2025-01-08",
        granularity="daily",
    )
    qs = dict(route.calls.last.request.url.params)
    assert qs["granularity"] == "daily"
    assert "delhi" in qs["state"]
    assert "maharashtra" in qs["state"]


def test_state_demand_unknown_state_raises_before_network(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="Unknown state slug"):
        client.get_state_demand("narnia", start="2025-01-01", end="2025-01-02")


# ---------------------------------------------------------------------------
# get_fuel_mix — live [IEA-324]
# ---------------------------------------------------------------------------

_FUEL_MIX_ROWS = [
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
    },
    {
        "timestamp": "2025-01-01T06:30:00+05:30",
        "state": "Gujarat",
        "state_slug": "gujarat",
        "thermal_mw": 8600.0,
        "hydro_mw": 350.0,
        "solar_mw": 120.0,
        "wind_mw": 610.0,
        "gas_mw": 1200.0,
        "nuclear_mw": 0.0,
        "renewable_mw": 50.0,
        "total_mw": 10930.0,
        "source": "canonical_store_v3",
        "source_kind": "modeled",
        "confidence": 0.85,
    },
]


@respx.mock
def test_fuel_mix_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/fuel-mix").mock(
        return_value=_items(_FUEL_MIX_ROWS)
    )
    df = client.get_fuel_mix("gujarat", start="2025-01-01", end="2025-01-02")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "thermal_mw" in df.columns
    assert "total_mw" in df.columns


@respx.mock
def test_fuel_mix_numeric_coercion(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/fuel-mix").mock(
        return_value=_items(_FUEL_MIX_ROWS)
    )
    df = client.get_fuel_mix("gujarat", start="2025-01-01", end="2025-01-02")
    assert df["thermal_mw"].dtype.kind == "f"
    assert df["total_mw"].dtype.kind == "f"


@respx.mock
def test_fuel_mix_passes_state_param(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/fuel-mix").mock(
        return_value=_items([])
    )
    client.get_fuel_mix("gujarat", start="2025-01-01", end="2025-01-08")
    qs = dict(route.calls.last.request.url.params)
    assert qs["state"] == "gujarat"


@respx.mock
def test_fuel_mix_passes_granularity(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/fuel-mix").mock(
        return_value=_items([])
    )
    client.get_fuel_mix("gujarat", start="2025-01-01", end="2025-01-08", granularity="daily")
    qs = dict(route.calls.last.request.url.params)
    assert qs["granularity"] == "daily"


def test_fuel_mix_unknown_state_raises_before_network(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="Unknown state slug"):
        client.get_fuel_mix("narnia", start="2025-01-01", end="2025-01-02")
