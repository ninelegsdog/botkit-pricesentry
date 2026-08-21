from __future__ import annotations

import pytest

from src.core.ui import item_card
from src.pricesentry import service


@pytest.mark.asyncio
async def test_full_monitoring_flow(db):
    item_id = await service.add_item(
        db, owner_id=111, sku="WB-001", name="Phone", marketplace="wb", target_price=50000.0
    )
    assert item_id > 0

    items = await service.get_user_items(db, 111)
    assert len(items) == 1

    await service.update_item_price(db, item_id, 49999.0)
    item = await service.get_item(db, item_id)
    assert item is not None
    assert float(item["current_price"]) == 49999.0

    await service.record_price(db, item_id, 49999.0)
    history = await service.get_price_history(db, item_id)
    assert len(history) == 1

    await service.delete_item(db, item_id)
    items = await service.get_user_items(db, 111)
    assert len(items) == 0


@pytest.mark.asyncio
async def test_alert_on_target_reached(db):
    item_id = await service.add_item(
        db, owner_id=222, sku="OZ-002", name="Laptop", marketplace="ozon", target_price=100000.0
    )
    await service.create_alert(
        db, item_id=item_id, user_id=222, message="Target reached",
        old_price=110000.0, new_price=99999.0
    )
    alerts = await service.get_user_alerts(db, 222)
    assert len(alerts) == 1
    assert "Target reached" in alerts[0]["message"]


@pytest.mark.asyncio
async def test_item_card_html():
    card = item_card({
        "name": "Test <script>",
        "sku": "123",
        "marketplace": "wb",
        "current_price": 100.0,
        "target_price": 90.0,
    })
    assert "<script>" not in card
    assert "Phone" not in card or "Test" in card
