"""Regulatory corpus tests (IEA-316).

search_orders + get_order against the CERC + 5 SERC structured corpus.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from india_energy_atlas import AtlasClient
from india_energy_atlas.exceptions import AtlasNotFoundError, AtlasValidationError

BASE = "https://api.test.example/v1"


@pytest.fixture
def client() -> AtlasClient:
    return AtlasClient(api_key="iea_test_key", base_url=BASE)


def _page(data: list[dict[str, Any]], next_cursor: str | None = None) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "next_cursor": next_cursor})


@respx.mock
def test_search_orders_returns_dataframe(client: AtlasClient) -> None:
    respx.get(f"{BASE}/regulatory/orders").mock(
        return_value=_page(
            [
                {
                    "order_id": "cerc/2024/178/2024-08-12",
                    "body": "cerc",
                    "issued_at": "2024-08-12T00:00:00+00:00",
                    "title": "Order on green tariff framework",
                    "petitioner": "MoP",
                    "respondent": "Various DISCOMs",
                    "tags": ["green-tariff", "rec"],
                    "url": "https://cercind.gov.in/2024/178.pdf",
                },
            ],
        )
    )
    df = client.search_orders(body="cerc", query="green tariff")
    assert df.iloc[0]["title"] == "Order on green tariff framework"
    assert df.iloc[0]["body"] == "cerc"


def test_search_orders_rejects_bad_body(client: AtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="body"):
        client.search_orders(body="foo", query="x")  # type: ignore[arg-type]


@respx.mock
def test_search_orders_passes_window(client: AtlasClient) -> None:
    route = respx.get(f"{BASE}/regulatory/orders").mock(return_value=_page([]))
    client.search_orders(
        body="cerc",
        query="tariff",
        issued_after="2024-01-01",
        issued_before="2024-12-31",
    )
    qs = dict(route.calls.last.request.url.params)
    assert qs["body"] == "cerc"
    assert qs["query"] == "tariff"
    assert qs["issued_after"] == "2024-01-01"
    assert qs["issued_before"] == "2024-12-31"


def test_search_orders_rejects_inverted_window(client: AtlasClient) -> None:
    with pytest.raises(AtlasValidationError, match="end"):
        client.search_orders(
            body="cerc",
            query="x",
            issued_after="2024-12-31",
            issued_before="2024-01-01",
        )


@respx.mock
def test_search_orders_paginates_transparently(client: AtlasClient) -> None:
    pages = iter(
        [
            _page(
                [{"order_id": f"cerc/2024/{i}/2024-01-01"} for i in range(3)],
                next_cursor="p2",
            ),
            _page(
                [{"order_id": f"cerc/2024/{i}/2024-01-01"} for i in range(3, 6)],
                next_cursor=None,
            ),
        ]
    )
    respx.get(f"{BASE}/regulatory/orders").mock(side_effect=lambda req: next(pages))
    df = client.search_orders(body="cerc", query="anything")
    assert len(df) == 6


@respx.mock
def test_get_order_returns_full_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/regulatory/orders/cerc/2024/178/2024-08-12").mock(
        return_value=httpx.Response(
            200,
            json={
                "order_id": "cerc/2024/178/2024-08-12",
                "body": "cerc",
                "issued_at": "2024-08-12",
                "title": "Order on green tariff framework",
                "parties": {
                    "petitioner": "MoP",
                    "respondents": ["BSES Rajdhani", "TPDDL"],
                },
                "prayer": "Direction to operationalise green tariff",
                "ratio": "Granted with modifications",
                "directions": [
                    {"para": 12, "text": "DISCOMs shall publish green tariff..."},
                ],
                "url": "https://cercind.gov.in/2024/178.pdf",
            },
        )
    )
    order = client.get_order("cerc/2024/178/2024-08-12")
    assert order["body"] == "cerc"
    assert order["parties"]["petitioner"] == "MoP"
    assert order["directions"][0]["para"] == 12


@respx.mock
def test_get_order_404_raises_not_found(client: AtlasClient) -> None:
    respx.get(f"{BASE}/regulatory/orders/no/such/order").mock(
        return_value=httpx.Response(404, json={"detail": "no such order"})
    )
    with pytest.raises(AtlasNotFoundError):
        client.get_order("no/such/order")


@respx.mock
def test_get_order_typeguard_on_non_dict(client: AtlasClient) -> None:
    respx.get(f"{BASE}/regulatory/orders/x").mock(return_value=httpx.Response(200, json=["a"]))
    with pytest.raises(TypeError):
        client.get_order("x")
