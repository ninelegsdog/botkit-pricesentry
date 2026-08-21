from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def client_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Мои товары"), KeyboardButton(text="➕ Добавить товар")],
            [KeyboardButton(text="🔔 Мои уведомления"), KeyboardButton(text="📊 Статистика")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Общая статистика")],
            [KeyboardButton(text="🔄 Проверить цены")],
        ],
        resize_keyboard=True,
    )
