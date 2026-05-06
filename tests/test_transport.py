"""Transport-layer tests using respx (httpx mock).

We use respx instead of pytest-recording/VCR for transport-level tests
because (a) the requests are not against a real server here and (b)
respx integrates natively with httpx.Client. Cassette-based VCR tests
will land alongside the typed methods in IEA-313+ where they have a
real API to record against.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from india_energy_atlas._transport import _build_user_agent, _HttpxTransport
from india_energy_atlas.exceptions import (
    AtlasAuthError,
    AtlasNotFoundError,
    AtlasRateLimitError,
    AtlasServerError,
    AtlasValidationError,
)

BASE = "https://api.test.example/v1"


def _transport(**overrides: object) -> _HttpxTransport:
    kwargs: dict[str, object] = {
        "base_url": BASE,
        "api_key": "iea_test_key",
        "timeout": 5.0,
        "max_retries": 2,
    }
    kwargs.update(overrides)
    return _HttpxTransport(**kwargs)  # type: ignore[arg-type]


@respx.mock
def test_happy_path_returns_json() -> None:
    respx.get(f"{BASE}/datasets").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "x"}]})
    )
    t = _transport()
    payload = t.request_json("GET", "/datasets")
    assert payload == {"data": [{"id": "x"}]}


@respx.mock
def test_authorization_header_sent() -> None:
    route = respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(200, json={"data": []}))
    t = _transport(api_key="iea_specific_key")
    t.request_json("GET", "/datasets")
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer iea_specific_key"


@respx.mock
def test_no_auth_header_when_no_key() -> None:
    route = respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(200, json={"data": []}))
    t = _transport(api_key=None)
    t.request_json("GET", "/datasets")
    sent = route.calls.last.request
    assert "Authorization" not in sent.headers


@respx.mock
def test_telemetry_user_agent_present_by_default() -> None:
    route = respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(200, json={"data": []}))
    t = _transport()
    t.request_json("GET", "/datasets")
    ua = route.calls.last.request.headers.get("User-Agent", "")
    assert ua.startswith("india-energy-atlas/")
    assert "py/" in ua
    assert "os/" in ua


@respx.mock
def test_telemetry_disabled_via_flag() -> None:
    route = respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(200, json={"data": []}))
    t = _transport(send_telemetry=False)
    t.request_json("GET", "/datasets")
    ua = route.calls.last.request.headers.get("User-Agent", "")
    assert not ua.startswith("india-energy-atlas/")


@respx.mock
def test_telemetry_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IEA_TELEMETRY", "0")
    route = respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(200, json={"data": []}))
    t = _transport()
    t.request_json("GET", "/datasets")
    ua = route.calls.last.request.headers.get("User-Agent", "")
    assert not ua.startswith("india-energy-atlas/")


@respx.mock
def test_404_raises_not_found() -> None:
    respx.get(f"{BASE}/datasets/missing").mock(
        return_value=httpx.Response(404, json={"detail": "no such dataset"})
    )
    t = _transport()
    with pytest.raises(AtlasNotFoundError):
        t.request_json("GET", "/datasets/missing")


@respx.mock
def test_401_raises_auth() -> None:
    respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(401, json={"detail": "bad key"}))
    t = _transport()
    with pytest.raises(AtlasAuthError):
        t.request_json("GET", "/datasets")


@respx.mock
def test_400_raises_validation() -> None:
    respx.get(f"{BASE}/datasets").mock(
        return_value=httpx.Response(400, json={"detail": "bad param"})
    )
    t = _transport()
    with pytest.raises(AtlasValidationError):
        t.request_json("GET", "/datasets")


@respx.mock
def test_422_raises_validation() -> None:
    respx.get(f"{BASE}/datasets").mock(
        return_value=httpx.Response(422, json={"detail": [{"loc": ["body"]}]})
    )
    t = _transport()
    with pytest.raises(AtlasValidationError):
        t.request_json("GET", "/datasets")


@respx.mock
def test_5xx_retries_then_raises() -> None:
    route = respx.get(f"{BASE}/datasets").mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    t = _transport(max_retries=2)
    with pytest.raises(AtlasServerError):
        t.request_json("GET", "/datasets")
    # 1 initial + 2 retries = 3 attempts total
    assert route.call_count == 3


@respx.mock
def test_5xx_recovers_on_retry() -> None:
    responses = iter(
        [
            httpx.Response(500, json={"detail": "transient"}),
            httpx.Response(200, json={"data": [{"id": "ok"}]}),
        ]
    )
    respx.get(f"{BASE}/datasets").mock(side_effect=lambda req: next(responses))
    t = _transport(max_retries=2)
    payload = t.request_json("GET", "/datasets")
    assert payload == {"data": [{"id": "ok"}]}


@respx.mock
def test_429_honours_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(time, "sleep", waits.append)

    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "0.1"}, json={"detail": "slow down"}),
            httpx.Response(200, json={"data": []}),
        ]
    )
    respx.get(f"{BASE}/datasets").mock(side_effect=lambda req: next(responses))
    t = _transport(max_retries=3)
    t.request_json("GET", "/datasets")
    assert waits == [0.1]


@respx.mock
def test_429_exhausts_retries_then_raises() -> None:
    respx.get(f"{BASE}/datasets").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={"detail": "limit"})
    )
    t = _transport(max_retries=1)
    with pytest.raises(AtlasRateLimitError):
        t.request_json("GET", "/datasets")


@respx.mock
def test_paginate_yields_all_rows_across_pages() -> None:
    pages = iter(
        [
            httpx.Response(
                200,
                json={"data": [{"i": 1}, {"i": 2}], "next_cursor": "abc"},
            ),
            httpx.Response(
                200,
                json={"data": [{"i": 3}, {"i": 4}], "next_cursor": None},
            ),
        ]
    )
    respx.get(f"{BASE}/datasets/x").mock(side_effect=lambda req: next(pages))
    t = _transport()
    rows = list(t.paginate("/datasets/x"))
    assert [r["i"] for r in rows] == [1, 2, 3, 4]


@respx.mock
def test_paginate_respects_limit() -> None:
    pages = iter(
        [
            httpx.Response(
                200, json={"data": [{"i": 1}, {"i": 2}, {"i": 3}], "next_cursor": "abc"}
            ),
            httpx.Response(200, json={"data": [{"i": 4}, {"i": 5}], "next_cursor": None}),
        ]
    )
    respx.get(f"{BASE}/datasets/x").mock(side_effect=lambda req: next(pages))
    t = _transport()
    rows = list(t.paginate("/datasets/x", limit=4))
    assert [r["i"] for r in rows] == [1, 2, 3, 4]


def test_user_agent_format() -> None:
    ua = _build_user_agent()
    parts = ua.split()
    assert parts[0].startswith("india-energy-atlas/")
    assert any(p.startswith("py/") for p in parts)
    assert any(p.startswith("os/") for p in parts)


@respx.mock
def test_context_manager_closes() -> None:
    respx.get(f"{BASE}/datasets").mock(return_value=httpx.Response(200, json={"data": []}))
    with _transport() as t:
        t.request_json("GET", "/datasets")
    # After exit, internal client should be closed; another call raises.
    with pytest.raises(RuntimeError):
        t._client.get("/datasets")
