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


async def delete_item(db: Database, item_id: int, user_id: int) -> bool:
    """Удаляет товар вместе с его историей цен и уведомлениями.

    Удаление разрешено только владельцу: `WHERE id = :id AND user_id = :uid`.
    При несовпадении владельца (или отсутствии товара) возвращает False и ничего
    не удаляет — одинаковый ответ на «нет такого» и «чужой», чтобы callback не
    стал оракулом существующих id (паттерн store/get_delivery).

    Прежнее мягкое удаление (is_active = 0) оставляло price_history с привязкой
    к item_id: история принадлежала товару только по совпадению номера, и в
    мультиарендной базе новый товар мог показать чужие цены. Схема объявляет
    ON DELETE CASCADE, но SQLite не применяет его без PRAGMA foreign_keys,
    поэтому чистим явно, в одной транзакции.
    """
    async with db.transaction() as session:
        # Сначала проверяем владение: если товар чужой/несуществующий — отказ.
        owner = await session.execute(
            text("SELECT 1 FROM monitored_items WHERE id = :id AND owner_id = :uid"),
            {"id": item_id, "uid": user_id},
        )
        if owner.first() is None:
            return False
        await session.execute(text("DELETE FROM price_history WHERE item_id = :id"), {"id": item_id})
        await session.execute(text("DELETE FROM alerts WHERE item_id = :id"), {"id": item_id})
        await session.execute(
            text("DELETE FROM monitored_items WHERE id = :id AND owner_id = :uid"),
            {"id": item_id, "uid": user_id},
        )
        return True


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


async def get_price_history(
    db: Database, item_id: int, user_id: int, limit: int = 10
) -> list[dict[str, Any]]:
    """История цен товара, но только если товар принадлежит user_id.

    Без фильтра по владельцу `hist:<id>` утекал историю чужих товаров.
    При чужом/несуществующем item_id возвращается пустой список — ответ
    «Нет истории цен.», не различающий «нет» и «чужой».
    """
    async with db.session() as session:
        # Проверяем владение до чтения истории.
        owner = await session.execute(
            text("SELECT 1 FROM monitored_items WHERE id = :id AND owner_id = :uid"),
            {"id": item_id, "uid": user_id},
        )
        if owner.first() is None:
            return []
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
