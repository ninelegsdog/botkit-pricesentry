from __future__ import annotations

import pytest

from src.pricesentry import service


@pytest.mark.asyncio
async def test_add_item(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    assert item_id > 0


@pytest.mark.asyncio
async def test_add_item_with_target(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="OZ-456", name="Laptop", marketplace="ozon", target_price=50000.0
    )
    assert item_id > 0


@pytest.mark.asyncio
async def test_get_user_items(db):
    await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    items = await service.get_user_items(db, 123)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_get_item(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    item = await service.get_item(db, item_id)
    assert item is not None
    assert item["sku"] == "WB-123"


@pytest.mark.asyncio
async def test_delete_item(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    await service.delete_item(db, item_id)
    items = await service.get_user_items(db, 123)
    assert len(items) == 0


@pytest.mark.asyncio
async def test_record_price(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    await service.record_price(db, item_id, 100.5)
    history = await service.get_price_history(db, item_id)
    assert len(history) == 1
    assert float(history[0]["price"]) == 100.5


@pytest.mark.asyncio
async def test_get_price_history_limit(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    for p in [100.0, 90.0, 80.0, 70.0, 60.0]:
        await service.record_price(db, item_id, p)
    history = await service.get_price_history(db, item_id, limit=3)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_create_alert(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    alert_id = await service.create_alert(
        db, item_id=item_id, user_id=123, message="Price dropped",
        old_price=100.0, new_price=80.0
    )
    assert alert_id > 0


@pytest.mark.asyncio
async def test_get_user_alerts(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    await service.create_alert(
        db, item_id=item_id, user_id=123, message="Alert 1"
    )
    alerts = await service.get_user_alerts(db, 123)
    assert len(alerts) == 1


@pytest.mark.asyncio
async def test_get_all_active_items(db):
    await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    items = await service.get_all_active_items(db)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_get_item_count(db):
    await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    await service.add_item(
        db, owner_id=456, sku="OZ-456", name="Laptop", marketplace="ozon"
    )
    count = await service.get_item_count(db)
    assert count == 2


@pytest.mark.asyncio
async def test_update_item_price(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    await service.update_item_price(db, item_id, 99.99)
    item = await service.get_item(db, item_id)
    assert item is not None
    assert float(item["current_price"]) == 99.99


@pytest.mark.asyncio
async def test_update_item_target(db):
    item_id = await service.add_item(
        db, owner_id=123, sku="WB-123", name="Phone", marketplace="wb"
    )
    await service.update_item_target(db, item_id, 50000.0)
    item = await service.get_item(db, item_id)
    assert item is not None
    assert float(item["target_price"]) == 50000.0
