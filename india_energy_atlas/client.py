"""Synchronous AtlasClient."""

from __future__ import annotations

import os
import warnings
from typing import Any, Literal

import pandas as pd

from india_energy_atlas._dataframes import (
    DEFAULT_TZ,
    coerce_numeric_columns,
    filter_by_window,
    rows_to_frame,
)
from india_energy_atlas._states import validate_state
from india_energy_atlas._transport import _HttpxTransport
from india_energy_atlas.exceptions import PreviewWarning

IexMarket = Literal["DAM", "RTM", "GDAM", "HP-DAM", "SCM"]

_NUMERIC_IEX_COLS = [
    "purchase_bid_mw",
    "sell_bid_mw",
    "mcv_mw",
    "mcp_rs_mwh",
    "mcp_inr_per_mwh",
]

_PREVIEW_WARNED: set[str] = set()


def _warn_preview_once(method_name: str, until: str) -> None:
    if method_name in _PREVIEW_WARNED:
        return
    _PREVIEW_WARNED.add(method_name)
    warnings.warn(
        f"{method_name} is Preview and may change before {until}. "
        f"See https://github.com/India-Energy-Atlas/india-energy-atlas#preview-apis",
        PreviewWarning,
        stacklevel=3,
    )


def _stringify(value: str | pd.Timestamp) -> str:
    if isinstance(value, pd.Timestamp):
        return str(value.isoformat())
    return str(value)


class AtlasClient:
    """Synchronous client for the India Energy Atlas data platform.

    Parameters
    ----------
    api_key:
        Atlas API key. Falls back to `$IEA_API_KEY`. `None` means
        unauthenticated (public datasets only).
    base_url:
        Override the API base URL. Defaults to `https://api.energymap.in`.
    timeout:
        Per-request timeout in seconds.
    send_telemetry:
        Send anonymous SDK version + Python version + OS in User-Agent.
        Defaults to True. Disable with `send_telemetry=False` or
        `IEA_TELEMETRY=0`.
    """

    DEFAULT_BASE_URL = "https://api.energymap.in"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        send_telemetry: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("IEA_API_KEY")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout
        self._transport = _HttpxTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
            send_telemetry=send_telemetry,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._transport.close()

    def __enter__(self) -> AtlasClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Check API health. Returns status, database, and workspace info."""
        payload = self._transport.request_json("GET", "/api/health")
        if not isinstance(payload, dict):
            raise TypeError(f"expected dict from /api/health, got {type(payload).__name__}")
        return payload

    # ------------------------------------------------------------------
    # States catalogue
    # ------------------------------------------------------------------

    def list_states(self) -> pd.DataFrame:
        """List all states in the Atlas catalogue.

        Returns a DataFrame with columns including ``state_slug``,
        ``state_name``, ``iso_code``, ``release_tier``, ``build_status``,
        ``completion_class``, and ``counts.*``.
        """
        rows = list(self._transport.paginate("/api/states"))
        return rows_to_frame(rows, timestamp_column=None)

    def get_state(self, slug: str) -> dict[str, Any]:
        """Return full per-state detail: counts, downloads, geometry.

        Parameters
        ----------
        slug:
            State slug, e.g. ``"delhi"``, ``"maharashtra"``.
        """
        payload = self._transport.request_json("GET", f"/api/states/{slug}")
        if not isinstance(payload, dict):
            raise TypeError(f"expected dict from /api/states/{slug}, got {type(payload).__name__}")
        return payload

    # ------------------------------------------------------------------
    # IEX market data
    # ------------------------------------------------------------------

    def get_iex_prices(
        self,
        market: IexMarket,
        *,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """IEX clearing prices for the given market segment.

        Parameters
        ----------
        market:
            One of ``DAM`` (Day-Ahead), ``RTM`` (Real-Time),
            ``GDAM`` (Green DAM), ``HP-DAM`` (High-Price DAM),
            ``SCM`` (Surplus Capacity Market).
        start, end:
            Optional ISO-8601 dates. Filtering is client-side until the
            backend exposes these params directly.

        Returns a DataFrame with columns ``timestamp``, ``market_type``,
        ``region``, ``purchase_bid_mw``, ``sell_bid_mw``, ``mcv_mw``,
        ``mcp_inr_per_mwh`` (renamed from ``mcp_rs_mwh`` for clarity),
        and ``source``. All MW and price columns are numeric.

        The rename ``mcp_rs_mwh`` -> ``mcp_inr_per_mwh`` is SDK-side only;
        the backend field is ``mcp_rs_mwh``.
        """
        params: dict[str, Any] = {"market_type": market}
        rows = list(self._transport.paginate("/api/intelligence/iex-market-data", params=params))
        df = rows_to_frame(rows, tz=tz)
        if df.empty:
            return df
        coerce_numeric_columns(df, _NUMERIC_IEX_COLS)
        if "mcp_rs_mwh" in df.columns:
            df = df.rename(columns={"mcp_rs_mwh": "mcp_inr_per_mwh"})
        df = filter_by_window(df, start, end, tz=tz)
        return df

    # ------------------------------------------------------------------
    # Carbon intensity
    # ------------------------------------------------------------------

    def get_carbon_intensity(
        self,
        *,
        state: str | None = None,
        discom: str | None = None,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Hourly carbon intensity for a state.

        Exactly one of ``state`` or ``discom`` must be provided.
        DISCOM-level addressing is not yet supported live; passing
        ``discom=`` raises ``NotImplementedError`` (landing in IEA-327).

        Returns a tz-aware DataFrame. The column ``carbon_intensity_gco2_kwh``
        from the API is renamed to ``gco2_per_kwh`` SDK-side.

        **Preview API.** Emits ``PreviewWarning`` on first call.
        """
        _warn_preview_once("get_carbon_intensity", until="2026-10-01")

        if discom is not None:
            from india_energy_atlas._discoms import validate_discom

            validate_discom(discom)
            params: dict[str, Any] = {"discom": discom}
            rows = list(
                self._transport.paginate("/api/intelligence/carbon-intensity", params=params)
            )
            df = rows_to_frame(rows, tz=tz)
            if df.empty:
                return df
            coerce_numeric_columns(
                df, ["carbon_intensity_gco2_kwh", "total_generation_mw", "confidence"]
            )
            if "carbon_intensity_gco2_kwh" in df.columns:
                df = df.rename(columns={"carbon_intensity_gco2_kwh": "gco2_per_kwh"})
            df = filter_by_window(df, start, end, tz=tz)
            return df

        if state is None:
            raise ValueError("state= must be provided")

        params: dict[str, Any] = {"state": state}
        rows = list(self._transport.paginate("/api/intelligence/carbon-intensity", params=params))
        df = rows_to_frame(rows, tz=tz)
        if df.empty:
            return df
        coerce_numeric_columns(
            df, ["carbon_intensity_gco2_kwh", "total_generation_mw", "confidence"]
        )
        if "carbon_intensity_gco2_kwh" in df.columns:
            df = df.rename(columns={"carbon_intensity_gco2_kwh": "gco2_per_kwh"})
        df = filter_by_window(df, start, end, tz=tz)
        return df

    # ------------------------------------------------------------------
    # Deferred methods — landing in IEA-323 through IEA-328
    # ------------------------------------------------------------------

    def list_datasets(self) -> pd.DataFrame:
        """Return catalogue of all available datasets as a DataFrame."""
        resp = self._transport.request_json("GET", "/api/datasets")
        rows = resp.get("items", [])
        return pd.DataFrame(rows)

    def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any]:
        """Return full metadata (including schema) for a single dataset."""
        return self._transport.request_json("GET", f"/api/datasets/{dataset_id}")

    def get_dataset(self, dataset_id: str, **kwargs: Any) -> pd.DataFrame:
        """Fetch a dataset by id, forwarding kwargs as query params.

        Looks up the endpoint from the catalogue then calls it with the
        provided keyword arguments (e.g. state=, start=, end=).
        """
        meta = self.get_dataset_metadata(dataset_id)
        endpoint = meta["endpoint"]
        rows = list(self._transport.paginate(endpoint, params=kwargs))
        return rows_to_frame(rows)

    def get_state_demand(
        self,
        states: list[str] | str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: Literal["hourly", "daily"] = "hourly",
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Hourly or daily state electricity demand.

        Parameters
        ----------
        states:
            One slug or a list of canonical slugs (e.g. ``"delhi"`` or
            ``["delhi", "maharashtra"]``). All slugs are validated against
            ``_states.CANONICAL_STATES`` before the network call.
        start, end:
            ISO-8601 date/timestamp bounds (inclusive start, exclusive end).
        granularity:
            ``"hourly"`` (default) or ``"daily"`` averages.
        tz:
            Timezone to use for the DataFrame index. Defaults to IST.

        Returns a tz-aware DataFrame indexed on ``timestamp``, with columns
        ``state``, ``demand_mw``, ``source``, ``provenance``, ``confidence``.
        The API field ``source_kind`` is renamed to ``provenance``.
        """
        slug_list: list[str] = [states] if isinstance(states, str) else list(states)
        for s in slug_list:
            validate_state(s)

        params: dict[str, Any] = {
            "state": ",".join(slug_list),
            "start": _stringify(start),
            "end": _stringify(end),
            "granularity": granularity,
        }
        rows = list(self._transport.paginate("/api/intelligence/state-demand", params=params))
        df = rows_to_frame(rows, tz=tz)
        if df.empty:
            return df
        coerce_numeric_columns(df, ["demand_mw", "confidence"])
        if "source_kind" in df.columns:
            df = df.rename(columns={"source_kind": "provenance"})
        return df

    def get_fuel_mix(
        self,
        state: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: Literal["hourly", "daily"] = "hourly",
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Hourly or daily fuel-mix breakdown for one state.

        Parameters
        ----------
        state:
            Canonical state slug (e.g. ``"gujarat"``, ``"delhi"``). Validated
            offline against ``_states.CANONICAL_STATES`` before the network call.
        start, end:
            ISO-8601 date/timestamp bounds (inclusive start, exclusive end).
        granularity:
            ``"hourly"`` (default) or ``"daily"``.
        tz:
            Timezone for the returned DataFrame index. Defaults to IST.

        Returns a tz-aware DataFrame indexed on ``timestamp``, with one column
        per fuel type (e.g. ``thermal_mw``, ``solar_mw``, ``wind_mw``) plus
        ``total_mw``, ``state``, ``state_slug``, ``source_kind``, and
        ``confidence``.
        """
        validate_state(state)
        params: dict[str, Any] = {
            "state": state,
            "start": _stringify(start),
            "end": _stringify(end),
            "granularity": granularity,
        }
        rows = list(self._transport.paginate("/api/intelligence/fuel-mix", params=params))
        df = rows_to_frame(rows, tz=tz)
        if df.empty:
            return df
        fuel_mw_cols = [c for c in df.columns if c.endswith("_mw")]
        coerce_numeric_columns(df, fuel_mw_cols)
        return df

    def get_frequency(
        self,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: Literal["1sec", "1min"] = "1min",
        region: Literal["NR", "WR", "SR", "ER", "NER"] | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Grid frequency observations per region.

        Parameters
        ----------
        start, end:
            ISO-8601 date/timestamp bounds (inclusive start, exclusive end).
        granularity:
            ``"1min"`` (default) or ``"1sec"`` (raises if coverage unavailable).
        region:
            One of NR/WR/SR/ER/NER. Omit for all regions.
        tz:
            Timezone for the DataFrame index. Defaults to IST.

        Returns a tz-aware DataFrame with columns ``region``, ``frequency_hz``,
        ``deviation_hz``, ``source``.
        """
        params: dict[str, Any] = {
            "start": _stringify(start),
            "end": _stringify(end),
            "granularity": granularity,
        }
        if region is not None:
            params["region"] = region
        rows = list(self._transport.paginate("/api/intelligence/frequency", params=params))
        df = rows_to_frame(rows, tz=tz)
        if df.empty:
            return df
        coerce_numeric_columns(df, ["frequency_hz", "deviation_hz"])
        return df

    def get_discom_metrics(
        self,
        discom: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        metrics: list[str] | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """DISCOM operational scorecard metrics (AT&C losses, billing/collection efficiency, etc.).

        Parameters
        ----------
        discom:
            Canonical DISCOM slug (e.g. ``"bses-rajdhani"``). Validated
            against ``_discoms.CANONICAL_DISCOMS`` before the network call.
        start, end:
            ISO-8601 date bounds.
        metrics:
            Optional list of metric codes to return (all if omitted).
        tz:
            Timezone for the DataFrame index. Defaults to IST.
        """
        from india_energy_atlas._discoms import validate_discom

        validate_discom(discom)

        params: dict[str, Any] = {
            "discom": discom,
            "start": _stringify(start),
            "end": _stringify(end),
        }
        if metrics:
            params["metrics"] = ",".join(metrics)
        rows = list(self._transport.paginate("/api/intelligence/discom-metrics", params=params))
        return rows_to_frame(rows, tz=tz)

    def search_orders(self, **kwargs: Any) -> pd.DataFrame:
        """Not yet live. Landing in IEA-328."""
        raise NotImplementedError(
            "/api/intelligence/regulatory-orders endpoint lands in IEA-328. "
            "Track progress at https://linear.app/sayon/issue/IEA-328"
        )

    def get_order(self, order_id: str) -> dict[str, Any]:
        """Not yet live. Landing in IEA-328."""
        raise NotImplementedError(
            "/api/intelligence/regulatory-orders endpoint lands in IEA-328. "
            "Track progress at https://linear.app/sayon/issue/IEA-328"
        )
