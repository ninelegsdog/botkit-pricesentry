from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.core.bot_factory import AppState
from src.core.fsm import AdminAuth
from src.core.nav import admin_menu, client_menu
from src.pricesentry import service


def create_admin_router(app_state: AppState) -> Router:
    router = Router()
    db = app_state.db

    def is_admin(user_id: int) -> bool:
        return user_id in (app_state.config.admin_ids or [])

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext) -> None:
        await state.set_state(AdminAuth.waiting_password)
        await message.answer("🔑 Введите пароль:")

    @router.message(AdminAuth.waiting_password)
    async def check_password(message: Message, state: FSMContext) -> None:
        if message.text == app_state.config.admin_password:
            await state.clear()
            await message.answer("✅ Добро пожаловать!", reply_markup=admin_menu())
        else:
            await state.clear()
            await message.answer("❌ Неверный пароль.", reply_markup=client_menu())

    @router.message(F.text == "📊 Общая статистика")
    async def admin_stats(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        count = await service.get_item_count(db)
        await message.answer(f"📊 Всего товаров в мониторинге: {count}")

    @router.message(F.text == "🔄 Проверить цены")
    async def admin_check_prices(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        await message.answer("🔄 Проверка цен запущена вручную (заглушка).")

    return router
