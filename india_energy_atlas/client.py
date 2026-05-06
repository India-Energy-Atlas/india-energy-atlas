"""Synchronous AtlasClient.

Discovery methods (`list_datasets`, `get_dataset_metadata`, `get_dataset`)
land here in IEA-313. Typed methods land in IEA-314+.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import pandas as pd

from india_energy_atlas._dataframes import DEFAULT_TZ, rows_to_frame
from india_energy_atlas._transport import _HttpxTransport

FilterOperator = Literal["=", "!=", ">", ">=", "<", "<=", "in", "not_in"]


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


def _stringify(value: str | pd.Timestamp) -> str:
    if isinstance(value, pd.Timestamp):
        return str(value.isoformat())
    return str(value)


def _stringify_filter_value(value: object) -> str:
    if isinstance(value, list | tuple):
        return ",".join(str(v) for v in value)
    return str(value)
