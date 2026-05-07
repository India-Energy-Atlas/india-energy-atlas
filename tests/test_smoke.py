"""Smoke tests — prove the package installs and imports cleanly."""

from __future__ import annotations

import re

import pytest

import india_energy_atlas
from india_energy_atlas import (
    AtlasAuthError,
    AtlasClient,
    AtlasError,
    AtlasNotFoundError,
    AtlasRateLimitError,
    AtlasServerError,
    AtlasValidationError,
    __version__,
)


def test_version_is_semver() -> None:
    assert re.match(r"^\d+\.\d+\.\d+", __version__), __version__


def test_version_attr_matches_module() -> None:
    assert india_energy_atlas.__version__ == __version__


def test_client_constructs_without_key() -> None:
    client = AtlasClient()
    assert client.base_url == AtlasClient.DEFAULT_BASE_URL
    assert client.timeout == AtlasClient.DEFAULT_TIMEOUT


def test_client_default_base_url_no_v1() -> None:
    assert "/v1" not in AtlasClient.DEFAULT_BASE_URL
    assert AtlasClient.DEFAULT_BASE_URL == "https://api.energymap.in"


def test_client_accepts_explicit_key() -> None:
    client = AtlasClient(api_key="iea_test_xyz")
    assert client.api_key == "iea_test_xyz"


def test_client_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IEA_API_KEY", "iea_env_abc")
    client = AtlasClient()
    assert client.api_key == "iea_env_abc"


def test_live_methods_exist() -> None:
    client = AtlasClient(api_key="iea_test")
    for method_name in (
        "health",
        "list_states",
        "get_state",
        "get_iex_prices",
        "get_carbon_intensity",
        "get_state_demand",
    ):
        assert callable(getattr(client, method_name)), method_name


def test_deferred_methods_exist() -> None:
    client = AtlasClient(api_key="iea_test")
    for method_name in (
        "list_datasets",
        "get_dataset_metadata",
        "get_dataset",
        "get_fuel_mix",
        "get_frequency",
        "get_discom_metrics",
        "search_orders",
        "get_order",
    ):
        assert callable(getattr(client, method_name)), method_name


def test_error_hierarchy() -> None:
    for cls in (
        AtlasAuthError,
        AtlasRateLimitError,
        AtlasNotFoundError,
        AtlasServerError,
        AtlasValidationError,
    ):
        assert issubclass(cls, AtlasError)
        assert issubclass(cls, Exception)
