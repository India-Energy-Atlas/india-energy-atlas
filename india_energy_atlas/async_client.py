"""Async sibling of `AtlasClient`.

Mirrors the sync surface method-for-method using `httpx.AsyncClient`.
Validation, DataFrame conversion, and the PreviewWarning machinery
are shared with the sync client.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import pandas as pd

from india_energy_atlas._async_transport import _AsyncHttpxTransport
from india_energy_atlas._dataframes import (
    DEFAULT_TZ,
    coerce_numeric_columns,
    filter_by_window,
    rows_to_frame,
)
from india_energy_atlas._states import validate_state
from india_energy_atlas.client import (
    IexMarket,
    _NUMERIC_IEX_COLS,
    _stringify,
    _warn_preview_once,
)


class AsyncAtlasClient:
    """Async counterpart of `AtlasClient`. See its docstring for params."""

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
        self._transport = _AsyncHttpxTransport(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
            send_telemetry=send_telemetry,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncAtlasClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Check API health."""
        payload = await self._transport.request_json("GET", "/api/health")
        if not isinstance(payload, dict):
            raise TypeError(f"expected dict from /api/health, got {type(payload).__name__}")
        return payload

    # ------------------------------------------------------------------
    # States catalogue
    # ------------------------------------------------------------------

    async def list_states(self) -> pd.DataFrame:
        """List all states in the Atlas catalogue."""
        rows = [r async for r in self._transport.paginate("/api/states")]
        return rows_to_frame(rows, timestamp_column=None)

    async def get_state(self, slug: str) -> dict[str, Any]:
        """Return full per-state detail."""
        payload = await self._transport.request_json("GET", f"/api/states/{slug}")
        if not isinstance(payload, dict):
            raise TypeError(f"expected dict from /api/states/{slug}, got {type(payload).__name__}")
        return payload

    # ------------------------------------------------------------------
    # IEX market data
    # ------------------------------------------------------------------

    async def get_iex_prices(
        self,
        market: IexMarket,
        *,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """IEX clearing prices. See `AtlasClient.get_iex_prices` for full docs."""
        params: dict[str, Any] = {"market_type": market}
        rows = [
            r
            async for r in self._transport.paginate(
                "/api/intelligence/iex-market-data", params=params
            )
        ]
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

    async def get_carbon_intensity(
        self,
        *,
        state: str | None = None,
        discom: str | None = None,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Hourly carbon intensity for a state. See `AtlasClient.get_carbon_intensity`."""
        _warn_preview_once("get_carbon_intensity", until="2026-10-01")

        if discom is not None:
            raise NotImplementedError(
                "DISCOM-level carbon intensity is not yet live. "
                "It lands in IEA-327 (/api/intelligence/discom-metrics). "
                "Use state= for now."
            )
        if state is None:
            raise ValueError("state= must be provided")

        params: dict[str, Any] = {"state": state}
        rows = [
            r
            async for r in self._transport.paginate(
                "/api/intelligence/carbon-intensity", params=params
            )
        ]
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
    # Deferred methods
    # ------------------------------------------------------------------

    async def list_datasets(self) -> pd.DataFrame:
        raise NotImplementedError(
            "/api/datasets catalogue endpoint lands in IEA-325. "
            "Track progress at https://linear.app/sayon/issue/IEA-325"
        )

    async def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "/api/datasets catalogue endpoint lands in IEA-325. "
            "Track progress at https://linear.app/sayon/issue/IEA-325"
        )

    async def get_dataset(self, dataset_id: str, **kwargs: Any) -> pd.DataFrame:
        raise NotImplementedError(
            "/api/datasets catalogue endpoint lands in IEA-325. "
            "Track progress at https://linear.app/sayon/issue/IEA-325"
        )

    async def get_state_demand(
        self,
        states: list[str] | str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: Literal["hourly", "daily"] = "hourly",
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Async equivalent of `AtlasClient.get_state_demand`."""
        slug_list: list[str] = [states] if isinstance(states, str) else list(states)
        for s in slug_list:
            validate_state(s)

        params: dict[str, Any] = {
            "state": ",".join(slug_list),
            "start": _stringify(start),
            "end": _stringify(end),
            "granularity": granularity,
        }
        rows = [r async for r in self._transport.paginate(
            "/api/intelligence/state-demand", params=params
        )]
        df = rows_to_frame(rows, tz=tz)
        if df.empty:
            return df
        coerce_numeric_columns(df, ["demand_mw", "confidence"])
        if "source_kind" in df.columns:
            df = df.rename(columns={"source_kind": "provenance"})
        return df

    async def get_fuel_mix(
        self,
        state: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: Literal["hourly", "daily"] = "hourly",
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Async equivalent of `AtlasClient.get_fuel_mix`."""
        validate_state(state)
        params: dict[str, Any] = {
            "state": state,
            "start": _stringify(start),
            "end": _stringify(end),
            "granularity": granularity,
        }
        rows = [r async for r in self._transport.paginate(
            "/api/intelligence/fuel-mix", params=params
        )]
        df = rows_to_frame(rows, tz=tz)
        if df.empty:
            return df
        fuel_mw_cols = [c for c in df.columns if c.endswith("_mw")]
        coerce_numeric_columns(df, fuel_mw_cols)
        return df

    async def get_frequency(self, **kwargs: Any) -> pd.DataFrame:
        raise NotImplementedError(
            "/api/intelligence/frequency endpoint lands in IEA-326. "
            "Track progress at https://linear.app/sayon/issue/IEA-326"
        )

    async def get_discom_metrics(self, discom: str, **kwargs: Any) -> pd.DataFrame:
        raise NotImplementedError(
            "/api/intelligence/discom-metrics endpoint lands in IEA-327. "
            "Track progress at https://linear.app/sayon/issue/IEA-327"
        )

    async def search_orders(self, **kwargs: Any) -> pd.DataFrame:
        raise NotImplementedError(
            "/api/intelligence/regulatory-orders endpoint lands in IEA-328. "
            "Track progress at https://linear.app/sayon/issue/IEA-328"
        )

    async def get_order(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "/api/intelligence/regulatory-orders endpoint lands in IEA-328. "
            "Track progress at https://linear.app/sayon/issue/IEA-328"
        )
