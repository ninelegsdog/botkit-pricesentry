from __future__ import annotations

import html
from typing import Any


def escape(text: str | None) -> str:
    return html.escape(str(text)) if text else ""


def item_card(item: dict[str, Any]) -> str:
    marketplace = str(item.get("marketplace", ""))
    current = float(item.get("current_price", 0))
    target = item.get("target_price")
    target_str = f"{float(target):.2f}" if target else "—"
    return (
        f"📦 {escape(str(item.get('name', '')))}\n"
        f"🛒 {marketplace} | SKU: {escape(str(item.get('sku', '')))}\n"
        f"💰 Текущая: {current:.2f} | Целевая: {target_str}"
    )


def alert_card(alert: dict[str, Any]) -> str:
    old_price = float(alert.get("old_price", 0)) if alert.get("old_price") else 0
    new_price = float(alert.get("new_price", 0)) if alert.get("new_price") else 0
    return (
        f"🔔 {escape(str(alert.get('message', '')))}\n"
        f"💰 {old_price:.2f} → {new_price:.2f}"
    )
