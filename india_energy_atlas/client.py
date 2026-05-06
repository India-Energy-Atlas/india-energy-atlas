"""Synchronous AtlasClient.

Constructor wires the transport. Typed methods land in IEA-313+.
"""

from __future__ import annotations

import os

from india_energy_atlas._transport import _HttpxTransport


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
    # Discovery (lands in IEA-313)
    # ------------------------------------------------------------------

    def list_datasets(self) -> object:
        """Return a DataFrame of available datasets. Implemented in IEA-313."""
        raise NotImplementedError("list_datasets lands in IEA-313")

    def get_dataset_metadata(self, dataset_id: str) -> object:
        """Return schema/units/provenance for a dataset. Implemented in IEA-313."""
        raise NotImplementedError("get_dataset_metadata lands in IEA-313")

    def get_dataset(self, dataset_id: str, **filters: object) -> object:
        """Generic escape hatch for any documented Atlas endpoint. Implemented in IEA-313."""
        raise NotImplementedError("get_dataset lands in IEA-313")
