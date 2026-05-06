"""Synchronous AtlasClient.

Discovery methods (`list_datasets`, `get_dataset_metadata`, `get_dataset`)
land here in IEA-313. Typed methods land in IEA-314+.
"""

from __future__ import annotations

import os
import warnings
from typing import Any, Literal

import pandas as pd

from india_energy_atlas._dataframes import DEFAULT_TZ, rows_to_frame
from india_energy_atlas._states import validate_state
from india_energy_atlas._transport import _HttpxTransport
from india_energy_atlas._validators import ensure_one_of, ensure_window
from india_energy_atlas.exceptions import PreviewWarning

FilterOperator = Literal["=", "!=", ">", ">=", "<", "<=", "in", "not_in"]
DemandGranularity = Literal["hourly", "15min", "daily"]
IexMarket = Literal["dam", "rtm", "gdam", "hp-dam", "scm"]
FrequencyGranularity = Literal["1sec", "1min"]
GridRegion = Literal["NR", "WR", "SR", "ER", "NER"]

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


class AtlasClient:
    """Synchronous client for the India Energy Atlas data platform.

    Parameters
    ----------
    api_key:
        Atlas API key. Falls back to `$IEA_API_KEY`. `None` means
        unauthenticated (public datasets only).
    base_url:
        Override the API base URL. Defaults to `https://api.energymap.in/v1`.
    timeout:
        Per-request timeout in seconds.
    send_telemetry:
        Send anonymous SDK version + Python version + OS in User-Agent.
        Defaults to True. Disable with `send_telemetry=False` or
        `IEA_TELEMETRY=0`.
    """

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
    # Discovery
    # ------------------------------------------------------------------

    def list_datasets(self) -> pd.DataFrame:
        """List every dataset available on the Atlas API.

        Returns a DataFrame with at least the columns
        ``dataset_id, title, granularity, coverage_start, coverage_end, tier``.
        """
        rows = list(self._transport.paginate("/datasets"))
        return rows_to_frame(rows, timestamp_column=None)

    def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any]:
        """Return schema, units, source, provenance, and refresh cadence for one dataset."""
        payload = self._transport.request_json("GET", f"/datasets/{dataset_id}")
        if not isinstance(payload, dict):
            raise TypeError(
                f"expected dict from /datasets/{dataset_id}, got {type(payload).__name__}"
            )
        return payload

    def get_dataset(
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
        """Generic dataset fetch with optional filter and time window.

        This is the escape-hatch method — every documented Atlas v1
        endpoint is reachable through it. Typed wrappers (e.g.
        ``get_state_demand``) build on top of this in IEA-314+.

        Parameters
        ----------
        dataset_id: str
        start, end: optional ISO-8601 dates / timestamps.
        columns: optional whitelist of columns to request server-side.
        filter_column / filter_operator / filter_value:
            Optional server-side filter. All three must be set together.
        limit: cap total rows returned. ``None`` means "everything".
        tz: timezone for the returned DataFrame index. Defaults to IST.
        """
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

        rows = list(
            self._transport.paginate(
                f"/datasets/{dataset_id}/rows",
                params=params,
                limit=limit,
            )
        )
        return rows_to_frame(rows, tz=tz)

    # ------------------------------------------------------------------
    # Typed methods (IEA-314)
    # ------------------------------------------------------------------

    def get_state_demand(
        self,
        states: list[str] | str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: DemandGranularity = "hourly",
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """SLDC demand for one or more states.

        Returns a tz-aware DataFrame with columns ``state``, ``demand_mw``,
        and ``provenance`` (``observed | modeled | synthesized | derived |
        missing``). Index is the timestamp.
        """
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
        rows = list(self._transport.paginate("/sldc/demand", params=params))
        return rows_to_frame(rows, tz=tz)

    def get_fuel_mix(
        self,
        state: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Hourly fuel-mix breakdown for one state.

        Columns include per-fuel MW (``coal_mw``, ``gas_mw``, ``hydro_mw``,
        ``solar_mw``, ``wind_mw``, ``nuclear_mw``, ``other_mw``) plus
        ``provenance``.
        """
        validated = validate_state(state)
        ensure_window(start, end)
        params: dict[str, Any] = {
            "state": validated,
            "start": _stringify(start),
            "end": _stringify(end),
        }
        rows = list(self._transport.paginate("/sldc/fuel-mix", params=params))
        return rows_to_frame(rows, tz=tz)

    def get_iex_prices(
        self,
        market: IexMarket,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """IEX clearing prices for the given market.

        ``market`` is one of ``dam`` (Day-Ahead), ``rtm`` (Real-Time),
        ``gdam`` (Green DAM), ``hp-dam`` (High-Price DAM), or ``scm``
        (Surplus Capacity Market). Returns a 15-min DataFrame with
        ``mcp_inr_per_mwh``, ``mcv_mw``, ``cleared_mw``, and ``area``.
        """
        ensure_one_of("market", market, ("dam", "rtm", "gdam", "hp-dam", "scm"))
        ensure_window(start, end)
        params: dict[str, Any] = {
            "market": market,
            "start": _stringify(start),
            "end": _stringify(end),
        }
        rows = list(self._transport.paginate("/iex/clearing-prices", params=params))
        return rows_to_frame(rows, tz=tz)

    # ------------------------------------------------------------------
    # Typed methods (IEA-315)
    # ------------------------------------------------------------------

    def get_carbon_intensity(
        self,
        *,
        discom: str | None = None,
        state: str | None = None,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Hourly carbon intensity, addressable by DISCOM or state.

        Exactly one of ``discom`` or ``state`` must be provided. Returns
        a tz-aware DataFrame with columns including ``gco2_per_kwh``,
        ``confidence``, and ``provenance`` (matches ies-ingest source_kind).

        **Preview API.** This method emits a ``PreviewWarning`` on first
        use because the underlying carbon-intensity dataset is marked
        Preview on energymap.in/ies until the DUM 2026 launch (October
        2026). The shape is stable; method signature may evolve.
        """
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

        rows = list(self._transport.paginate("/carbon/intensity", params=params))
        return rows_to_frame(rows, tz=tz)

    def get_discom_metrics(
        self,
        discom: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        metrics: list[str] | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Daily DISCOM operational metrics.

        Returns a daily-frequency DataFrame with one column per requested
        metric (or all 70+ if ``metrics`` is None). Common metrics:
        ``collection_efficiency``, ``billing_efficiency``, ``atc_loss``,
        ``acs_arr_gap_inr_per_kwh``.
        """
        ensure_window(start, end)
        params: dict[str, Any] = {
            "discom": discom,
            "start": _stringify(start),
            "end": _stringify(end),
        }
        if metrics:
            params["metrics"] = ",".join(metrics)
        rows = list(self._transport.paginate("/discom/metrics", params=params))
        return rows_to_frame(rows, tz=tz)

    def get_frequency(
        self,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        granularity: FrequencyGranularity = "1min",
        region: GridRegion | None = None,
        tz: str = DEFAULT_TZ,
    ) -> pd.DataFrame:
        """Grid frequency observations.

        Returns a tz-aware DataFrame with ``frequency_hz`` and ``region``
        (one of NR / WR / SR / ER / NER). If ``region`` is set, results
        are filtered to that region; otherwise all five regions are
        interleaved.
        """
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
        rows = list(self._transport.paginate("/grid/frequency", params=params))
        return rows_to_frame(rows, tz=tz)


def _stringify(value: str | pd.Timestamp) -> str:
    if isinstance(value, pd.Timestamp):
        return str(value.isoformat())
    return str(value)


def _stringify_filter_value(value: object) -> str:
    if isinstance(value, list | tuple):
        return ",".join(str(v) for v in value)
    return str(value)
