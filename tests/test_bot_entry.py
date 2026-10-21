"""Вебхук-режим должен запускать фоновую проверку цен (дефект F1).

В проде бот работает через webhook: `_run_webhook` поднимает HTTP-сервер и
регистрирует вебхук, но до правки фоновый `price_check_loop` создавался
только в `_run_polling` — то есть на проде мониторинг цен молчал бесконечно,
а `/health` при этом отвечал ok. Тест ловит регресс: цикл обязан реально
стартовать до shutdown, иначе `started.wait()` не дождётся и упадёт таймаут.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot import _run_webhook


@pytest.mark.asyncio
async def test_webhook_mode_starts_price_check_loop(monkeypatch):
    started = asyncio.Event()

    async def fake_loop(bot, db, interval=21600):
        started.set()
        await asyncio.sleep(3600)  # до отмены при shutdown

    monkeypatch.setattr("src.bot.price_check_loop", fake_loop)

    state = MagicMock()
    state.dp.emit_startup = AsyncMock()
    state.dp.emit_shutdown = AsyncMock()
    state.config.webhook_url = "https://example.invalid/hook"
    state.config.webhook_secret = "s3cret"
    state.config.metrics_port = 0  # эфемерный порт: тест ничего не занимает
    state.bot.delete_webhook = AsyncMock()
    state.bot.set_webhook = AsyncMock()

    shutdown = asyncio.Event()
    task = asyncio.create_task(_run_webhook(state, shutdown))
    await asyncio.wait_for(started.wait(), timeout=5)
    shutdown.set()
    await asyncio.wait_for(task, timeout=5)
