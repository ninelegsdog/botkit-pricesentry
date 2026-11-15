"""State-dependent view tests for pricesentry."""

from __future__ import annotations

import pytest

from src.pricesentry import service


@pytest.mark.asyncio
async def test_user_items_empty_vs_populated(db):
    assert await service.get_user_items(db, owner_id=1) == []

    await service.add_item(db, owner_id=1, sku="A", name="Item A", marketplace="wb")
    items = await service.get_user_items(db, owner_id=1)
    assert len(items) == 1
    assert items[0]["name"] == "Item A"


@pytest.mark.asyncio
async def test_user_items_active_vs_inactive(db):
    await service.add_item(db, owner_id=1, sku="A", name="Active", marketplace="wb")
    await service.add_item(db, owner_id=1, sku="B", name="Inactive", marketplace="wb")

    async with db.transaction() as session:
        from sqlalchemy import text

        await session.execute(text("UPDATE monitored_items SET is_active = 0 WHERE sku = 'B'"))

    items = await service.get_user_items(db, owner_id=1)
    names = [i["name"] for i in items]
    assert "Active" in names
    assert "Inactive" not in names


@pytest.mark.asyncio
async def test_get_item_missing_vs_present(db):
    assert await service.get_item(db, 99999) is None

    item_id = await service.add_item(db, owner_id=1, sku="A", name="P", marketplace="wb")
    item = await service.get_item(db, item_id)
    assert item is not None
    assert item["name"] == "P"


@pytest.mark.asyncio
async def test_price_history_empty_vs_populated(db):
    item_id = await service.add_item(db, owner_id=1, sku="A", name="P", marketplace="wb")
    assert await service.get_price_history(db, item_id, user_id=1) == []

    await service.record_price(db, item_id, 100.0)
    history = await service.get_price_history(db, item_id, user_id=1)
    assert len(history) == 1
    assert history[0]["price"] == 100.0


@pytest.mark.asyncio
async def test_alerts_empty_vs_populated(db):
    item_id = await service.add_item(db, owner_id=1, sku="A", name="P", marketplace="wb")
    assert await service.get_user_alerts(db, user_id=1) == []

    await service.create_alert(db, item_id=item_id, user_id=1, message="drop", old_price=100, new_price=80)
    alerts = await service.get_user_alerts(db, user_id=1)
    assert len(alerts) == 1
