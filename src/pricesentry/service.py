from __future__ import annotations

from typing import Any

from sqlalchemy import text

from src.core.database import Database


async def add_item(
    db: Database,
    *,
    owner_id: int,
    sku: str,
    name: str,
    marketplace: str,
    target_price: float | None = None,
    url: str | None = None,
) -> int:
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "INSERT INTO monitored_items (sku, name, marketplace, target_price, owner_id, url) "
                "VALUES (:sku, :name, :mp, :tp, :owner, :url)"
            ),
            {
                "sku": sku,
                "name": name,
                "mp": marketplace,
                "tp": target_price,
                "owner": owner_id,
                "url": url,
            },
        )
        item_id = result.lastrowid  # type: ignore[attr-defined]
        assert item_id is not None
        return int(item_id)


async def get_user_items(db: Database, owner_id: int) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM monitored_items WHERE owner_id = :owner AND is_active = 1"),
            {"owner": owner_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_item(db: Database, item_id: int) -> dict[str, Any] | None:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM monitored_items WHERE id = :id"), {"id": item_id}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def delete_item(db: Database, item_id: int) -> None:
    async with db.transaction() as session:
        await session.execute(
            text("UPDATE monitored_items SET is_active = 0 WHERE id = :id"), {"id": item_id}
        )


async def update_item_price(db: Database, item_id: int, new_price: float) -> None:
    async with db.transaction() as session:
        await session.execute(
            text(
                "UPDATE monitored_items SET current_price = :price, updated_at = datetime('now') "
                "WHERE id = :id"
            ),
            {"price": new_price, "id": item_id},
        )


async def update_item_target(db: Database, item_id: int, target_price: float) -> None:
    async with db.transaction() as session:
        await session.execute(
            text("UPDATE monitored_items SET target_price = :tp WHERE id = :id"),
            {"tp": target_price, "id": item_id},
        )


async def record_price(db: Database, item_id: int, price: float) -> None:
    async with db.transaction() as session:
        await session.execute(
            text("INSERT INTO price_history (item_id, price) VALUES (:item, :price)"),
            {"item": item_id, "price": price},
        )


async def get_price_history(db: Database, item_id: int, limit: int = 10) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM price_history WHERE item_id = :item ORDER BY checked_at DESC LIMIT :lim"
            ),
            {"item": item_id, "lim": limit},
        )
        return [dict(r) for r in result.mappings().all()]


async def create_alert(
    db: Database,
    *,
    item_id: int,
    user_id: int,
    message: str,
    old_price: float | None = None,
    new_price: float | None = None,
) -> int:
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "INSERT INTO alerts (item_id, user_id, message, old_price, new_price) "
                "VALUES (:item, :user, :msg, :old, :new)"
            ),
            {"item": item_id, "user": user_id, "msg": message, "old": old_price, "new": new_price},
        )
        alert_id = result.lastrowid  # type: ignore[attr-defined]
        assert alert_id is not None
        return int(alert_id)


async def get_user_alerts(db: Database, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM alerts WHERE user_id = :user ORDER BY sent_at DESC LIMIT :lim"),
            {"user": user_id, "lim": limit},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_all_active_items(db: Database) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM monitored_items WHERE is_active = 1")
        )
        return [dict(r) for r in result.mappings().all()]


async def get_item_count(db: Database) -> int:
    async with db.session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM monitored_items WHERE is_active = 1"))
        row = result.fetchone()
        return int(row[0]) if row else 0
