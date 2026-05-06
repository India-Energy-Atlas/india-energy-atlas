"""Async sibling of `_transport._HttpxTransport`.

Shares the helper functions with the sync transport so retry policy,
status-code mapping, and telemetry behave identically. Only the I/O
boundary differs.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from india_energy_atlas._transport import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PAGE_SIZE,
    _build_user_agent,
    _exception_for_status,
    _parse_retry_after,
    _telemetry_enabled,
)
from india_energy_atlas.exceptions import AtlasError, AtlasServerError


class _AsyncHttpxTransport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout: float,
        send_telemetry: bool = True,
        max_retries: int = DEFAULT_MAX_RETRIES,
        client: httpx.AsyncClient | None = None,
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

        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> _AsyncHttpxTransport:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: object | None = None,
    ) -> Any:
        attempt = 0
        backoff = DEFAULT_BACKOFF_BASE
        while True:
            attempt += 1
            try:
                response = await self._client.request(method, path, params=params, json=json)
            except httpx.TransportError as e:
                if attempt > self.max_retries:
                    raise AtlasServerError(f"transport error after {attempt} attempts: {e}") from e
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            status = response.status_code
            if 200 <= status < 300:
                if not response.content:
                    return None
                return response.json()

            if status == 429 and attempt <= self.max_retries:
                wait = _parse_retry_after(response.headers) or backoff
                await asyncio.sleep(wait)
                backoff *= 2
                continue

            if 500 <= status < 600 and attempt <= self.max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            try:
                body = response.json()
            except ValueError:
                body = response.text
            err: AtlasError = _exception_for_status(status, body)
            raise err

    async def paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[dict[str, Any]]:
        emitted = 0
        cursor: str | None = None
        base_params: dict[str, Any] = dict(params or {})
        base_params["page_size"] = page_size

        while True:
            page_params = dict(base_params)
            if cursor is not None:
                page_params["cursor"] = cursor

            payload = await self.request_json("GET", path, params=page_params)
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
