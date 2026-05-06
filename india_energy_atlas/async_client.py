"""Async sibling of `AtlasClient`.

Mirrors the sync surface method-for-method using `httpx.AsyncClient`.
Validation, state allowlist, DataFrame conversion, and the
PreviewWarning machinery are shared with the sync client.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from india_energy_atlas._async_transport import _AsyncHttpxTransport
from india_energy_atlas._dataframes import DEFAULT_TZ, rows_to_frame
from india_energy_atlas._states import validate_state
from india_energy_atlas._validators import ensure_one_of, ensure_window
from india_energy_atlas.client import (
    DemandGranularity,
    FilterOperator,
    FrequencyGranularity,
    GridRegion,
    IexMarket,
    RegulatoryBody,
    _stringify,
    _stringify_filter_value,
    _warn_preview_once,
)


class AsyncAtlasClient:
    """Async counterpart of `AtlasClient`. See its docstring for params."""

    DEFAULT_BASE_URL = "https://api.energymap.in/v1"
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
    # Discovery
    # ------------------------------------------------------------------

    async def list_datasets(self) -> pd.DataFrame:
        rows = [r async for r in self._transport.paginate("/datasets")]
        return rows_to_frame(rows, timestamp_column=None)

    async def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any]:
        payload = await self._transport.request_json("GET", f"/datasets/{dataset_id}")
        if not isinstance(payload, dict):
            raise TypeError(
                f"expected dict from /datasets/{dataset_id}, got {type(payload).__name__}"
            )
        return payload

    async def get_dataset(
        self,
        dataset_id: str,
        *,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        columns: list[str] | None = None,
        filter_column: str | None = None,
        filter_operator: FilterOperator | None = None,
        filter_value: object = None,
        limit: int | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = _stringify(start)
        if end is not None:
            params["end"] = _stringify(end)
        if columns:
            params["columns"] = ",".join(columns)
        if filter_column or filter_operator or filter_value is not None:
            if not (filter_column and filter_operator and filter_value is not None):
                raise ValueError(
                    "filter_column, filter_operator, and filter_value must all be set together"
                )
            params["filter_column"] = filter_column
            params["filter_operator"] = filter_operator
            params["filter_value"] = _stringify_filter_value(filter_value)

        rows = [
            r
            async for r in self._transport.paginate(
                f"/datasets/{dataset_id}/rows",
                params=params,
                limit=limit,
            )
        ]
        return rows_to_frame(rows, tz=tz)

    # ------------------------------------------------------------------
    # Typed methods
    # ------------------------------------------------------------------

    async def get_state_demand(
        self,
        states: list[str] | str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: DemandGranularity = "hourly",
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        ensure_one_of("granularity", granularity, ("hourly", "15min", "daily"))
        ensure_window(start, end)
        if isinstance(states, str):
            states = [states]
        validated = [validate_state(s) for s in states]
        params: dict[str, Any] = {
            "start": _stringify(start),
            "end": _stringify(end),
            "granularity": granularity,
            "states": ",".join(validated),
        }
        rows = [r async for r in self._transport.paginate("/sldc/demand", params=params)]
        return rows_to_frame(rows, tz=tz)

    async def get_fuel_mix(
        self,
        state: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        validated = validate_state(state)
        ensure_window(start, end)
        params: dict[str, Any] = {
            "state": validated,
            "start": _stringify(start),
            "end": _stringify(end),
        }
        rows = [r async for r in self._transport.paginate("/sldc/fuel-mix", params=params)]
        return rows_to_frame(rows, tz=tz)

    async def get_iex_prices(
        self,
        market: IexMarket,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        ensure_one_of("market", market, ("dam", "rtm", "gdam", "hp-dam", "scm"))
        ensure_window(start, end)
        params: dict[str, Any] = {
            "market": market,
            "start": _stringify(start),
            "end": _stringify(end),
        }
        rows = [r async for r in self._transport.paginate("/iex/clearing-prices", params=params)]
        return rows_to_frame(rows, tz=tz)

    async def get_carbon_intensity(
        self,
        *,
        discom: str | None = None,
        state: str | None = None,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        _warn_preview_once("get_carbon_intensity", until="2026-10-01")
        if (discom is None) == (state is None):
            raise ValueError("Exactly one of discom= or state= must be provided")
        ensure_window(start, end)
        params: dict[str, Any] = {
            "start": _stringify(start),
            "end": _stringify(end),
        }
        if discom is not None:
            params["discom"] = discom
        else:
            assert state is not None
            params["state"] = validate_state(state)
        rows = [r async for r in self._transport.paginate("/carbon/intensity", params=params)]
        return rows_to_frame(rows, tz=tz)

    async def get_discom_metrics(
        self,
        discom: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        metrics: list[str] | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        ensure_window(start, end)
        params: dict[str, Any] = {
            "discom": discom,
            "start": _stringify(start),
            "end": _stringify(end),
        }
        if metrics:
            params["metrics"] = ",".join(metrics)
        rows = [r async for r in self._transport.paginate("/discom/metrics", params=params)]
        return rows_to_frame(rows, tz=tz)

    async def get_frequency(
        self,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: FrequencyGranularity = "1min",
        region: GridRegion | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        ensure_one_of("granularity", granularity, ("1sec", "1min"))
        ensure_window(start, end)
        if region is not None:
            ensure_one_of("region", region, ("NR", "WR", "SR", "ER", "NER"))
        params: dict[str, Any] = {
            "start": _stringify(start),
            "end": _stringify(end),
            "granularity": granularity,
        }
        if region is not None:
            params["region"] = region
        rows = [r async for r in self._transport.paginate("/grid/frequency", params=params)]
        return rows_to_frame(rows, tz=tz)

    # ------------------------------------------------------------------
    # Regulatory corpus
    # ------------------------------------------------------------------

    async def search_orders(
        self,
        *,
        body: RegulatoryBody,
        query: str,
        issued_after: str | pd.Timestamp | None = None,
        issued_before: str | pd.Timestamp | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        ensure_one_of("body", body, ("cerc", "derc", "mserc", "jverc", "opserc", "tnerc"))
        ensure_window(issued_after, issued_before)
        params: dict[str, Any] = {"body": body, "query": query}
        if issued_after is not None:
            params["issued_after"] = _stringify(issued_after)
        if issued_before is not None:
            params["issued_before"] = _stringify(issued_before)
        rows = [
            r
            async for r in self._transport.paginate(
                "/regulatory/orders", params=params, limit=limit
            )
        ]
        return rows_to_frame(rows, timestamp_column="issued_at")

    async def get_order(self, order_id: str) -> dict[str, Any]:
        payload = await self._transport.request_json("GET", f"/regulatory/orders/{order_id}")
        if not isinstance(payload, dict):
            raise TypeError(
                f"expected dict from /regulatory/orders/{order_id}, got {type(payload).__name__}"
            )
        return payload
