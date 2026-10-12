from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.core.auth import AdminGate
from src.core.bot_factory import AppState
from src.core.fsm import AdminAuth
from src.core.nav import admin_menu, client_menu
from src.pricesentry import service


def create_admin_router(app_state: AppState) -> Router:
    router = Router()
    db = app_state.db

    def is_admin(user_id: int) -> bool:
        return user_id in (app_state.config.admin_ids or [])

    # The password check below compared in constant time but had no attempt
    # limit, so the admin surface allowed unlimited guesses. AdminGate adds the
    # throttle; is_throttled is checked BEFORE authorize so guesses are refused
    # for the whole window. is_admin keeps its old meaning: config admins, plus
    # anyone the gate has authorised.
    gate = AdminGate(
        app_state.config.admin_password, app_state.config.admin_ids or []
    )

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext) -> None:
        await state.set_state(AdminAuth.waiting_password)
        await message.answer("🔑 Введите пароль:")

    @router.message(AdminAuth.waiting_password)
    async def check_password(message: Message, state: FSMContext) -> None:
        user_id = message.from_user.id  # type: ignore[union-attr]
        if gate.is_throttled(user_id):
            await state.clear()
            await message.answer(
                "⏳ Слишко много попыток. "
                "Попробуйте через 5 минут.",
                reply_markup=client_menu(),
            )
            return
        if gate.authorize(user_id, message.text or ""):
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
