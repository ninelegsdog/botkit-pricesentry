from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ItemAdd(StatesGroup):
    entering_sku = State()
    choosing_marketplace = State()
    entering_name = State()
    entering_target_price = State()
    entering_url = State()
    confirming = State()


class ItemEdit(StatesGroup):
    choosing_item = State()
    editing_field = State()


class AdminAuth(StatesGroup):
    waiting_password = State()
