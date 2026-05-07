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


def test_carbon_intensity_unknown_discom_raises_value_error(client: AtlasClient) -> None:
    with pytest.warns(PreviewWarning):
        with pytest.raises(ValueError, match="Unknown DISCOM slug"):
            client.get_carbon_intensity(discom="fake-discom-xyz")


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


# ---------------------------------------------------------------------------
# list_datasets / get_dataset_metadata / get_dataset — live [IEA-325]
# ---------------------------------------------------------------------------

_CATALOGUE_ITEMS = [
    {"dataset_id": "state_demand", "title": "SLDC State Electricity Demand",
     "endpoint": "/api/intelligence/state-demand", "tier": "free"},
    {"dataset_id": "fuel_mix", "title": "State Hourly Fuel Mix",
     "endpoint": "/api/intelligence/fuel-mix", "tier": "free"},
]

_STATE_DEMAND_META = {
    "dataset_id": "state_demand",
    "title": "SLDC State Electricity Demand",
    "endpoint": "/api/intelligence/state-demand",
    "tier": "free",
    "coverage_start": "2022-01-01",
    "schema": [{"name": "timestamp", "type": "timestamptz"},
               {"name": "demand_mw", "type": "double"}],
}


@respx.mock
def test_list_datasets_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/datasets").mock(
        return_value=httpx.Response(200, json={"items": _CATALOGUE_ITEMS, "count": 2})
    )
    df = client.list_datasets()
    assert isinstance(df, pd.DataFrame)
    assert list(df["dataset_id"]) == ["state_demand", "fuel_mix"]


@respx.mock
def test_get_dataset_metadata_returns_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/datasets/state_demand").mock(
        return_value=httpx.Response(200, json=_STATE_DEMAND_META)
    )
    meta = client.get_dataset_metadata("state_demand")
    assert isinstance(meta, dict)
    assert meta["dataset_id"] == "state_demand"
    assert "schema" in meta


@respx.mock
def test_get_dataset_proxies_to_endpoint(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/datasets/state_demand").mock(
        return_value=httpx.Response(200, json=_STATE_DEMAND_META)
    )
    demand_rows = [{"timestamp": "2025-01-01T05:30:00+05:30", "state": "Delhi",
                    "demand_mw": 4200.0}]
    respx.get(f"{BASE}/api/intelligence/state-demand").mock(
        return_value=httpx.Response(200, json={"items": demand_rows, "count": 1})
    )
    df = client.get_dataset("state_demand", state="delhi", start="2025-01-01", end="2025-01-02")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1


# ---------------------------------------------------------------------------
# get_frequency — live [IEA-326]
# ---------------------------------------------------------------------------

_FREQUENCY_ROWS = [
    {
        "timestamp": "2025-01-01T00:00:00+00:00",
        "region": "NR",
        "frequency_hz": 49.985,
        "deviation_hz": -0.015,
        "source": "rldc_telemetry",
    },
    {
        "timestamp": "2025-01-01T00:01:00+00:00",
        "region": "NR",
        "frequency_hz": 50.012,
        "deviation_hz": 0.012,
        "source": "rldc_telemetry",
    },
]


@respx.mock
def test_frequency_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/frequency").mock(
        return_value=_items(_FREQUENCY_ROWS)
    )
    df = client.get_frequency(start="2025-01-01", end="2025-01-02")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "frequency_hz" in df.columns
    assert "deviation_hz" in df.columns


@respx.mock
def test_frequency_numeric_coercion(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/frequency").mock(
        return_value=_items(_FREQUENCY_ROWS)
    )
    df = client.get_frequency(start="2025-01-01", end="2025-01-02")
    assert df["frequency_hz"].dtype.kind == "f"
    assert df["deviation_hz"].dtype.kind == "f"


@respx.mock
def test_frequency_passes_region_param(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/frequency").mock(return_value=_items([]))
    client.get_frequency(start="2025-01-01", end="2025-01-02", region="NR")
    qs = dict(route.calls.last.request.url.params)
    assert qs["region"] == "NR"


@respx.mock
def test_frequency_passes_granularity(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/frequency").mock(return_value=_items([]))
    client.get_frequency(start="2025-01-01", end="2025-01-02", granularity="1min")
    qs = dict(route.calls.last.request.url.params)
    assert qs["granularity"] == "1min"


# ---------------------------------------------------------------------------
# get_discom_metrics — live [IEA-327]
# ---------------------------------------------------------------------------

_DISCOM_ROWS = [
    {
        "timestamp": "2024-03-31",
        "discom_slug": "bses-rajdhani",
        "atc_losses": 7.2,
        "billing_efficiency": 93.1,
        "collection_efficiency": 99.5,
        "source": "annual_report",
        "source_kind": "observed",
        "confidence": 0.9,
    }
]


@respx.mock
def test_discom_metrics_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/discom-metrics").mock(
        return_value=_items(_DISCOM_ROWS)
    )
    df = client.get_discom_metrics("bses-rajdhani", start="2024-01-01", end="2025-01-01")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1


def test_discom_metrics_unknown_slug_raises_before_network(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="Unknown DISCOM slug"):
        client.get_discom_metrics("fake-discom", start="2024-01-01", end="2025-01-01")


@respx.mock
def test_discom_metrics_passes_params(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/api/intelligence/discom-metrics").mock(return_value=_items([]))
    client.get_discom_metrics(
        "bses-rajdhani", start="2024-01-01", end="2025-01-01",
        metrics=["atc_losses", "billing_efficiency"],
    )
    qs = dict(route.calls.last.request.url.params)
    assert qs["discom"] == "bses-rajdhani"
    assert "atc_losses" in qs["metrics"]


@respx.mock
def test_carbon_intensity_discom_calls_api(client: AtlasClient) -> None:
    respx.get(f"{BASE}/api/intelligence/carbon-intensity").mock(
        return_value=_items([{"timestamp": "2025-01-01T00:00:00+00:00", "carbon_intensity_gco2_kwh": 494.0}])
    )
    with pytest.warns(PreviewWarning):
        df = client.get_carbon_intensity(discom="bses-rajdhani")
    assert isinstance(df, pd.DataFrame)
    assert "gco2_per_kwh" in df.columns
