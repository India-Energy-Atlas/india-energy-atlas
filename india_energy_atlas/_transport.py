"""Internal HTTP transport.

Wraps a single `httpx.Client`. Handles:
  - Bearer auth from `AtlasClient.api_key`
  - Default timeout
  - Retry-on-5xx with exponential backoff (max 3 attempts)
  - `Retry-After` honoured on 429
  - Telemetry User-Agent (opt-out)
  - Status code -> exception mapping
  - Cursor-pagination iterator

Public API: `_HttpxTransport.request_json` and `_HttpxTransport.paginate`.
Everything else is private.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from collections.abc import Iterator
from typing import Any

import httpx

from india_energy_atlas._version import __version__
from india_energy_atlas.exceptions import (
    AtlasAuthError,
    AtlasError,
    AtlasNotFoundError,
    AtlasRateLimitError,
    AtlasServerError,
    AtlasValidationError,
)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5  # seconds
DEFAULT_PAGE_SIZE = 1000


def _build_user_agent() -> str:
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    osname = platform.system().lower()
    return f"india-energy-atlas/{__version__} py/{py} os/{osname}"


def _telemetry_enabled(flag: bool) -> bool:
    if not flag:
        return False
    env = os.environ.get("IEA_TELEMETRY", "1").strip().lower()
    return env not in ("0", "false", "no", "off")


def _exception_for_status(status: int, body: object) -> AtlasError:
    if status == 401:
        return AtlasAuthError(f"401 Unauthorized: {body!r}")
    if status == 404:
        return AtlasNotFoundError(f"404 Not Found: {body!r}")
    if status in (400, 422):
        return AtlasValidationError(f"{status} Validation: {body!r}")
    if status == 429:
        err = AtlasRateLimitError(f"429 Rate limit exceeded: {body!r}")
        return err
    if 500 <= status < 600:
        return AtlasServerError(f"{status} Server error: {body!r}")
    return AtlasError(f"{status}: {body!r}")


def _parse_retry_after(headers: httpx.Headers) -> float | None:
    raw = headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        # HTTP-date form not supported; surface None and let caller decide.
        return None


class _HttpxTransport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout: float,
        send_telemetry: bool = True,
        max_retries: int = DEFAULT_MAX_RETRIES,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        headers: dict[str, str] = {"Accept": "application/json"}
        if _telemetry_enabled(send_telemetry):
            headers["User-Agent"] = _build_user_agent()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> _HttpxTransport:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: object | None = None,
    ) -> Any:
        """Single request with retry. Returns decoded JSON body or raises an `AtlasError`."""
        attempt = 0
        backoff = DEFAULT_BACKOFF_BASE
        while True:
            attempt += 1
            try:
                response = self._client.request(method, path, params=params, json=json)
            except httpx.TransportError as e:
                if attempt > self.max_retries:
                    raise AtlasServerError(f"transport error after {attempt} attempts: {e}") from e
                time.sleep(backoff)
                backoff *= 2
                continue

            status = response.status_code
            if 200 <= status < 300:
                if not response.content:
                    return None
                return response.json()

            if status == 429 and attempt <= self.max_retries:
                wait = _parse_retry_after(response.headers) or backoff
                time.sleep(wait)
                backoff *= 2
                continue

            if 500 <= status < 600 and attempt <= self.max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue

            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise _exception_for_status(status, body)

    def paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[dict[str, Any]]:
        """Yield rows from a cursor-paginated endpoint.

        The Atlas API contract: paginated GETs return
        `{"data": [...], "next_cursor": <string|null>}`. This helper hides
        the cursor handshake. Stops when `limit` is reached or the cursor
        is `null`.
        """
        emitted = 0
        cursor: str | None = None
        base_params: dict[str, Any] = dict(params or {})
        base_params["page_size"] = page_size

        while True:
            page_params = dict(base_params)
            if cursor is not None:
                page_params["cursor"] = cursor

            payload = self.request_json("GET", path, params=page_params)
            if payload is None:
                return

            rows = payload.get("data", [])
            for row in rows:
                if limit is not None and emitted >= limit:
                    return
                yield row
                emitted += 1

            cursor = payload.get("next_cursor")
            if cursor is None:
                return
