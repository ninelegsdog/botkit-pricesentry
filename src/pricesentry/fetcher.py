from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PriceSentry/1.0)"}
_TIMEOUT = 10.0

# Allowed domains for SSRF protection
ALLOWED_DOMAINS = {
    # Wildberries
    "wildberries.ru",
    "www.wildberries.ru",
    "card.wbstatic.net",
    "static.wbstatic.net",
    "wbstatic.net",
    # Ozon
    "ozon.ru",
    "www.ozon.ru",
    "cdn.ozon.ru",
    "static.ozon.ru",
}

_PRICE_RE = re.compile(r"(\d[\d\s]*)\s?(?:₽|руб\.)")


def _validate_url(url: str) -> bool:
    """Validate URL against allowed domains to prevent SSRF."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        # Check exact match or subdomain match
        return any(
            hostname == domain or hostname.endswith("." + domain)
            for domain in ALLOWED_DOMAINS
        )
    except Exception:
        return False


async def fetch_html(url: str) -> str:
    if not _validate_url(url):
        raise ValueError(f"URL not in allowed domains: {url}")
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _extract_jsonld_price(html: str) -> float | None:
    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data: Any = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            offers = node.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
                if price is not None:
                    try:
                        return float(price)
                    except (TypeError, ValueError):
                        pass
    return None


def _extract_meta_price(html: str) -> float | None:
    match = re.search(
        r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([\d.]+)["\']',
        html,
        re.IGNORECASE,
    )
    if match is None:
        match = re.search(
            r'<meta[^>]+content=["\']([\d.]+)["\'][^>]+property=["\']product:price:amount["\']',
            html,
            re.IGNORECASE,
        )
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_regex_price(html: str) -> float | None:
    match = _PRICE_RE.search(html)
    if match is None:
        return None
    digits = match.group(1).replace(" ", "").replace("\xa0", "")
    try:
        return float(digits)
    except ValueError:
        return None


def extract_price(html: str) -> float | None:
    """Three-strategy price extraction: JSON-LD → og meta → currency regex."""
    return (
        _extract_jsonld_price(html)
        or _extract_meta_price(html)
        or _extract_regex_price(html)
    )


async def fetch_price(url: str) -> float | None:
    html = await fetch_html(url)
    return extract_price(html)
