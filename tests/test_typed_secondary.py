"""Tests for IEA-315 typed methods.

get_carbon_intensity (Preview), get_discom_metrics, get_frequency.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
import respx

from india_energy_atlas import AtlasClient, PreviewWarning
from india_energy_atlas.client import _PREVIEW_WARNED
from india_energy_atlas.exceptions import AtlasValidationError


@contextmanager
def warnings_caught() -> Iterator[list[warnings.WarningMessage]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield caught


BASE = "https://api.test.example/v1"


@pytest.fixture
def client() -> AtlasClient:
    return AtlasClient(api_key="iea_test_key", base_url=BASE)


@pytest.fixture(autouse=True)
def _clear_preview_warned() -> None:
    _PREVIEW_WARNED.clear()


def _page(data: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "next_cursor": None})


# ---------------------------------------------------------------------------
# get_carbon_intensity
# ---------------------------------------------------------------------------


@respx.mock
def test_carbon_intensity_by_discom_emits_preview_warning(client: AtlasClient) -> None:
    respx.get(f"{BASE}/carbon/intensity").mock(
        return_value=_page(
            [
                {
                    "timestamp": "2025-06-01T00:00:00+00:00",
                    "discom": "bses-rajdhani",
                    "gco2_per_kwh": 690.5,
                    "confidence": 0.82,
                    "provenance": "derived",
                },
            ]
        )
    )
    with pytest.warns(PreviewWarning, match="get_carbon_intensity"):
        df = client.get_carbon_intensity(
            discom="bses-rajdhani",
            start="2025-06-01",
            end="2025-06-02",
        )
    assert df.iloc[0]["gco2_per_kwh"] == 690.5
    assert df.iloc[0]["provenance"] == "derived"


@respx.mock
def test_carbon_intensity_warning_emits_only_once(client: AtlasClient) -> None:
    respx.get(f"{BASE}/carbon/intensity").mock(return_value=_page([]))
    with pytest.warns(PreviewWarning):
        client.get_carbon_intensity(state="delhi", start="2025-06-01", end="2025-06-02")
    # Second call: no warning.
    with warnings_caught() as caught:
        client.get_carbon_intensity(state="delhi", start="2025-06-01", end="2025-06-02")
    assert not any(isinstance(w.message, PreviewWarning) for w in caught)


@respx.mock
def test_carbon_intensity_state_path_validates_slug(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="Unknown state slug"):
        client.get_carbon_intensity(state="atlantis", start="2025-06-01", end="2025-06-02")


def test_carbon_intensity_requires_one_of_discom_or_state(client: AtlasClient) -> None:
    with pytest.raises(ValueError, match="Exactly one"):
        client.get_carbon_intensity(start="2025-06-01", end="2025-06-02")
    with pytest.raises(ValueError, match="Exactly one"):
        client.get_carbon_intensity(discom="x", state="delhi", start="2025-06-01", end="2025-06-02")


# ---------------------------------------------------------------------------
# get_discom_metrics
# ---------------------------------------------------------------------------


@respx.mock
def test_discom_metrics_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/discom/metrics").mock(
        return_value=_page(
            [
                {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "discom": "bses-rajdhani",
                    "collection_efficiency": 0.97,
                    "billing_efficiency": 0.91,
                    "atc_loss": 0.12,
                },
            ]
        )
    )
    df = client.get_discom_metrics("bses-rajdhani", start="2025-01-01", end="2025-12-31")
    assert "collection_efficiency" in df.columns
    assert df.iloc[0]["atc_loss"] == 0.12


@respx.mock
def test_discom_metrics_passes_metrics_filter(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/discom/metrics").mock(return_value=_page([]))
    client.get_discom_metrics(
        "bses-rajdhani",
        start="2025-01-01",
        end="2025-12-31",
        metrics=["atc_loss", "collection_efficiency"],
    )
    qs = dict(route.calls.last.request.url.params)
    assert qs["metrics"] == "atc_loss,collection_efficiency"


# ---------------------------------------------------------------------------
# get_frequency
# ---------------------------------------------------------------------------


@respx.mock
def test_frequency_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/grid/frequency").mock(
        return_value=_page(
            [
                {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "frequency_hz": 49.98,
                    "region": "NR",
                },
            ]
        )
    )
    df = client.get_frequency(start="2025-01-01", end="2025-01-02")
    assert df.iloc[0]["frequency_hz"] == 49.98
    assert df.iloc[0]["region"] == "NR"


def test_frequency_rejects_bad_granularity(client: AtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="granularity"):
        client.get_frequency(
            start="2025-01-01",
            end="2025-01-02",
            granularity="hourly",  # type: ignore[arg-type]
        )


def test_frequency_rejects_bad_region(client: AtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="region"):
        client.get_frequency(
            start="2025-01-01",
            end="2025-01-02",
            region="Pacific",  # type: ignore[arg-type]
        )


@respx.mock
def test_frequency_passes_region_when_set(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/grid/frequency").mock(return_value=_page([]))
    client.get_frequency(start="2025-01-01", end="2025-01-02", region="WR")
    qs = dict(route.calls.last.request.url.params)
    assert qs["region"] == "WR"
