from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}
_TIMEOUT = 10.0
_MAX_RETRIES = 2

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
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS
            ) as client:
                resp = await client.get(url)
                # 4xx (включая 498 anti-bot) — не ретраим, это не временная ошибка.
                if 400 <= resp.status_code < 500:
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPStatusError as exc:
            if 400 <= exc.response.status_code < 500:
                raise
            last_exc = exc
        except httpx.RequestError as exc:
            last_exc = exc
        if attempt < _MAX_RETRIES:
            await asyncio.sleep(1.0 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


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
