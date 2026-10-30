from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from src.core.database import Database
from src.pricesentry import service

logger = logging.getLogger(__name__)


async def price_check_loop(bot: Bot, db: Database, interval: int = 21600) -> None:
    from src.pricesentry.fetcher import fetch_price
    from src.core.metrics import PRICE_FETCH_FAILURES_TOTAL

    if interval <= 0:
        # Признак «проверка выключена» (SCHEDULER_INTERVAL=0): не делаем
        # ни одной работы — негатив F1: выключенный цикл не трогает данные.
        logger.warning("Price check disabled (interval=%s)", interval)
        return

    while True:
        try:
            items = await service.get_all_active_items(db)
            for item in items:
                try:
                    item_id = int(item["id"])
                    url = item.get("url")
                    if url:
                        try:
                            fetched = await fetch_price(str(url))
                        except Exception as exc:
                            # Один заблокированный URL (живой факт: WB
                            # отвечает 498) не должен убивать весь цикл —
                            # товар остаётся на цене из БД, остальные идут дальше.
                            fetched = None
                            PRICE_FETCH_FAILURES_TOTAL.inc()
                            logger.warning("Price fetch failed for item %s: %s", item_id, exc)
                        if fetched is not None and fetched != float(item.get("current_price", 0)):
                            await service.update_item_price(db, item_id, fetched)
                    current = await _fresh_price(db, item_id)
                    await service.record_price(db, item_id, current)
                    target = item.get("target_price")
                    if target is not None and current <= float(target):
                        old = float(item.get("current_price", 0))
                        await service.create_alert(
                            db,
                            item_id=item_id,
                            user_id=int(item["owner_id"]),
                            message=f"Цена снизилась: {item.get('name', '')}",
                            old_price=old,
                            new_price=current,
                        )
                        await bot.send_message(
                            int(item["owner_id"]),
                            f"🔔 Цена снизилась!\n"
                            f"📦 {item.get('name', '')}\n"
                            f"💰 {current:.2f} ≤ целевая {float(target):.2f}",
                        )
                except Exception:
                    logger.exception("Price check failed for item %s", item.get("id"))
        except Exception:
            logger.exception("Price check error")
        await asyncio.sleep(interval)


async def _fresh_price(db: Database, item_id: int) -> float:
    item = await service.get_item(db, item_id)
    return float(item["current_price"]) if item else 0.0
