from __future__ import annotations

import pytest

from src.core.config import Config
from src.core.ui import alert_card, escape, item_card


@pytest.mark.asyncio
async def test_config_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    config = Config.from_env()
    assert config.bot_token == "test_token"


def test_escape():
    assert escape("<script>") == "&lt;script&gt;"
    assert escape("hello") == "hello"
    assert escape(None) == ""


def test_item_card():
    card = item_card({
        "name": "Test <item>",
        "sku": "123",
        "marketplace": "wb",
        "current_price": 100.5,
        "target_price": 90.0,
    })
    assert "<item>" not in card
    assert "100.50" in card


def test_item_card_no_target():
    card = item_card({
        "name": "Item",
        "sku": "456",
        "marketplace": "ozon",
        "current_price": 50.0,
        "target_price": None,
    })
    assert "—" in card


def test_alert_card():
    card = alert_card({
        "message": "Price dropped",
        "old_price": 100.0,
        "new_price": 80.0,
    })
    assert "100.00" in card
    assert "80.00" in card
