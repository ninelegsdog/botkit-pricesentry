from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.bot_factory import AppState
from src.core.fsm import ItemAdd
from src.core.nav import client_menu
from src.core.ui import alert_card, escape, item_card
from src.pricesentry import service


def create_pricesentry_router(app_state: AppState) -> Router:
    router = Router()
    db = app_state.db

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        await message.answer(
            "📦 Мониторинг цен на маркетплейсах!",
            reply_markup=client_menu(),
        )

    @router.message(F.text == "➕ Добавить товар")
    async def start_add(message: Message, state: FSMContext) -> None:
        await state.set_state(ItemAdd.entering_sku)
        await message.answer("🔍 Введите SKU товара:")

    @router.message(ItemAdd.entering_sku)
    async def enter_sku(message: Message, state: FSMContext) -> None:
        await state.update_data(sku=message.text or "")
        await state.set_state(ItemAdd.choosing_marketplace)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Wildberries", callback_data="mp:wb")],
                [InlineKeyboardButton(text="Ozon", callback_data="mp:ozon")],
            ]
        )
        await message.answer("🛒 Выберите маркетплейс:", reply_markup=kb)

    @router.callback_query(F.data.startswith("mp:"))
    async def choose_marketplace(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        marketplace = callback.data.split(":")[1]
        await state.update_data(marketplace=marketplace)
        await state.set_state(ItemAdd.entering_name)
        await callback.message.edit_text("📝 Название товара:")  # type: ignore[union-attr]
        await callback.answer()

    @router.message(ItemAdd.entering_name)
    async def enter_name(message: Message, state: FSMContext) -> None:
        await state.update_data(name=message.text or "")
        await state.set_state(ItemAdd.entering_target_price)
        await message.answer("🎯 Целевая цена (или пропустите):")

    @router.message(ItemAdd.entering_target_price)
    async def enter_target_price(message: Message, state: FSMContext) -> None:
        text = message.text or ""
        try:
            target_price = float(text)
        except ValueError:
            target_price = None
        await state.update_data(target_price=target_price)
        await state.set_state(ItemAdd.entering_url)
        await message.answer("🔗 Ссылка на товар (или - чтобы пропустить):")

    @router.message(ItemAdd.entering_url)
    async def enter_url(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        url = None if raw in ("-", "/skip") else (raw if raw.startswith("http") else None)
        await state.update_data(url=url)
        data = await state.get_data()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Добавить", callback_data="item_confirm"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="item_cancel"),
                ]
            ]
        )
        await state.set_state(ItemAdd.confirming)
        target_price = data.get("target_price")
        target_str = f"{target_price:.2f}" if target_price else "—"
        await message.answer(
            f"Добавить товар?\n"
            f"📦 {escape(str(data.get('name', '')))}\n"
            f"🛒 {escape(str(data.get('marketplace', '')))}\n"
            f"🎯 Целевая: {target_str}\n"
            f"🔗 URL: {data.get('url') or '—'}",
            reply_markup=kb,
        )

    @router.callback_query(F.data == "item_confirm", ItemAdd.confirming)
    async def confirm_add(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        await service.add_item(
            db,
            owner_id=callback.from_user.id,
            sku=str(data.get("sku", "")),
            name=str(data.get("name", "")),
            marketplace=str(data.get("marketplace", "")),
            target_price=data.get("target_price"),
            url=data.get("url"),
        )
        await state.clear()
        await callback.message.edit_text("✅ Товар добавлен!")  # type: ignore[union-attr]
        await callback.answer()
        await callback.message.answer("Выберите действие:", reply_markup=client_menu())  # type: ignore[union-attr]

    @router.callback_query(F.data == "item_cancel")
    async def cancel_add(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.message.edit_text("Отменено.")  # type: ignore[union-attr]
        await callback.answer()
        await callback.message.answer("Выберите действие:", reply_markup=client_menu())  # type: ignore[union-attr]

    @router.message(F.text == "📦 Мои товары")
    async def my_items(message: Message) -> None:
        items = await service.get_user_items(db, message.from_user.id)  # type: ignore[union-attr]
        if not items:
            await message.answer("Нет мониторинга.")
            return
        for it in items:
            card = item_card(it)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📊 История", callback_data=f"hist:{it['id']}"),
                        InlineKeyboardButton(text="❌ Удалить", callback_data=f"del:{it['id']}"),
                    ]
                ]
            )
            await message.answer(card, reply_markup=kb)

    @router.callback_query(F.data.startswith("hist:"))
    async def show_history(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        item_id = int(callback.data.split(":")[1])
        history = await service.get_price_history(db, item_id, limit=5)
        if not history:
            await callback.message.edit_text("Нет истории цен.")  # type: ignore[union-attr]
        else:
            lines = [f"💰 {h['price']:.2f} ({h['checked_at']})" for h in history]
            await callback.message.edit_text("📊 История цен:\n" + "\n".join(lines))  # type: ignore[union-attr]
        await callback.answer()

    @router.callback_query(F.data.startswith("del:"))
    async def delete_item(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        item_id = int(callback.data.split(":")[1])
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data=f"del_yes:{item_id}"),
                    InlineKeyboardButton(text="❌ Нет", callback_data="del_no"),
                ]
            ]
        )
        await callback.message.edit_text("❓ Удалить товар?", reply_markup=kb)  # type: ignore[union-attr]
        await callback.answer()

    @router.callback_query(F.data.startswith("del_yes:"))
    async def confirm_delete(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        item_id = int(callback.data.split(":")[1])
        await service.delete_item(db, item_id)
        await callback.message.edit_text("✅ Товар удалён.")  # type: ignore[union-attr]
        await callback.answer()

    @router.callback_query(F.data == "del_no")
    async def cancel_delete(callback: CallbackQuery) -> None:
        await callback.message.edit_text("Оставлено.")  # type: ignore[union-attr]
        await callback.answer()

    @router.message(F.text == "🔔 Мои уведомления")
    async def my_alerts(message: Message) -> None:
        alerts = await service.get_user_alerts(db, message.from_user.id)  # type: ignore[union-attr]
        if not alerts:
            await message.answer("Нет уведомлений.")
            return
        for a in alerts[:5]:
            await message.answer(alert_card(a))

    @router.message(F.text == "📊 Статистика")
    async def stats(message: Message) -> None:
        items = await service.get_user_items(db, message.from_user.id)  # type: ignore[union-attr]
        await message.answer(f"📊 Ваши товары: {len(items)}")

    return router
