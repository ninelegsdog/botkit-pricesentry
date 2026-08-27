from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from src.pricesentry.fetcher import extract_price, fetch_price

JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "Product", "name": "Widget", "offers": {"price": "1499.90", "priceCurrency": "RUB"}}
</script>
</head><body>Buy the widget!</body></html>
"""

META_HTML = """
<html><head>
<meta property="og:title" content="Widget">
<meta property="product:price:amount" content="899.50">
</head><body></body></html>
"""

REGEX_HTML = """<html><body><div>Цена: 3 499 ₽ только сегодня!</div></body></html>"""

NO_PRICE_HTML = "<html><body>nothing here</body></html>"


def test_jsonld_price() -> None:
    assert extract_price(JSONLD_HTML) == 1499.90


def test_meta_price() -> None:
    assert extract_price(META_HTML) == 899.50


def test_regex_price_with_spaces() -> None:
    assert extract_price(REGEX_HTML) == 3499.0


def test_no_price_returns_none() -> None:
    assert extract_price(NO_PRICE_HTML) is None


def test_jsonld_priority_over_meta() -> None:
    html = JSONLD_HTML.replace("</script>", "</script>") + META_HTML
    assert extract_price(html) == 1499.90


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (json.dumps({"offers": {"price": 123}}), 123.0),
        (json.dumps([{"@type": "Product"}, {"offers": {"price": "77"}}]), 77.0),
        ("not json at all", None),
    ],
)
def test_jsonld_edge_cases(payload: str, expected: float | None) -> None:
    html = f'<script type="application/ld+json">{payload}</script>'
    assert extract_price(html) == expected


async def test_fetch_price_via_fake_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=JSONLD_HTML)

    transport = httpx.MockTransport(handler)
    import src.pricesentry.fetcher as fetcher_mod

    class _Client(httpx.AsyncClient):
        def __init__(self, **kwargs: Any) -> None:
            kwargs.pop("transport", None)
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr(fetcher_mod.httpx, "AsyncClient", _Client)
    price = await fetch_price("https://www.wildberries.ru/widget")
    assert price == 1499.90
