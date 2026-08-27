from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User

from src.admin.handlers import create_admin_router
from src.core.auth import AuthMiddleware
from src.core.bot_factory import AppState, create_app
from src.core.config import Config
from src.core.errors import RetryMiddleware, default_error_handler, register_error_handler
from src.core.fsm import AdminAuth, ItemAdd, ItemEdit
from src.core.metrics import UPDATES_TOTAL, Metrics, UpdatesMiddleware
from src.core.nav import admin_menu, client_menu
from src.core.payments import MockPaymentProvider, PaymentProvider
from src.core.sentry import init_sentry
from src.core.storage import Storage
from src.core.throttling import ThrottlingMiddleware
from src.core.webhook import create_app as create_webhook_app
from src.pricesentry.handlers import create_pricesentry_router
from src.scheduler.loop import price_check_loop


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def test_config_from_env_reads_plain_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "tok")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")
    monkeypatch.setenv("ADMIN_IDS", "1,2,3")
    monkeypatch.setenv("REDIS_URL", "redis://h:1")
    cfg = Config.from_env()
    assert cfg.bot_token == "tok"
    assert cfg.admin_password == "pw"
    assert cfg.admin_ids == [1, 2, 3]
    assert cfg.redis_url == "redis://h:1"


def test_config_validate_raises_when_missing(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    cfg = Config(bot_token="", admin_password="", admin_ids=[])
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        cfg.validate()
    cfg.bot_token = "x"
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        cfg.validate()
    cfg.admin_password = "y"
    with pytest.raises(RuntimeError, match="ADMIN_IDS"):
        cfg.validate()
    cfg.admin_ids = [1]
    cfg.validate()


# --------------------------------------------------------------------------- #
# bot_factory
# --------------------------------------------------------------------------- #
def test_create_app_builds_bot_and_storage():
    with patch("src.core.bot_factory.RedisStorage.from_url", return_value=MemoryStorage()):
        state = create_app(Config(bot_token="123456789:AAfake", admin_ids=[1]))
    assert isinstance(state, AppState)
    assert isinstance(state.bot, Bot)
    assert state.config.bot_token == "123456789:AAfake"
    assert state.fsm_storage is not None


# --------------------------------------------------------------------------- #
# ThrottlingMiddleware
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_throttling_throttles_messages_only():
    mw = ThrottlingMiddleware(min_interval=2.0)
    handler = AsyncMock(return_value="ok")
    user = User(id=1, is_bot=False, first_name="U")
    msg = Message(message_id=1, chat=Chat(id=1, type="private"), date=datetime.now(), from_user=user, text="x")

    assert await mw(handler, msg, {}) == "ok"
    handler.reset_mock()
    assert await mw(handler, msg, {}) is None
    assert handler.await_count == 0
    assert await mw(handler, object(), {}) is not None


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_storage_get_set_setting():
    sess = MagicMock()
    sess.execute = AsyncMock()
    sess.execute.return_value.fetchone = MagicMock(return_value=("val",))
    cm = AsyncMock()
    cm.__aenter__.return_value = sess
    cm.__aexit__.return_value = False
    fake_db = MagicMock()
    fake_db.session = MagicMock(return_value=cm)
    fake_db.transaction = MagicMock(return_value=cm)

    storage = Storage(fake_db)
    assert await storage.get_setting("k") == "val"
    await storage.set_setting("k", "v")
    sess.execute.assert_awaited()


# --------------------------------------------------------------------------- #
# Webhook
# --------------------------------------------------------------------------- #
def test_webhook_create_app_returns_aiohttp_app():
    app = create_webhook_app(AppState(Config(bot_token="123456789:AAfake", admin_ids=[1])))
    assert callable(app.router.routes)
    paths = {r.resource.canonical for r in app.router.routes()}
    assert "/health" in paths
    assert "/metrics" in paths


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def test_metrics_inc_and_uptime():
    m = Metrics()
    m.inc_messages()
    m.inc_prices_checked()
    m.inc_alerts_sent()
    m.inc_errors()
    assert m.messages_processed == 1
    assert m.prices_checked == 1
    assert m.alerts_sent == 1
    assert m.errors == 1
    assert m.uptime_seconds() >= 0


@pytest.mark.asyncio
async def test_updates_middleware_increments_prom_counter():
    class MyEvent:
        pass

    before = UPDATES_TOTAL.labels(type="myevent")._value.get()
    handler = AsyncMock(return_value="r")
    assert await UpdatesMiddleware()(handler, MyEvent(), {}) == "r"
    after = UPDATES_TOTAL.labels(type="myevent")._value.get()
    assert after == before + 1


# --------------------------------------------------------------------------- #
# Sentry
# --------------------------------------------------------------------------- #
def test_sentry_no_dsn_silent():
    init_sentry(None)


def test_sentry_missing_sdk():
    with patch.dict("sys.modules", {"sentry_sdk": None}):
        init_sentry("https://abc@sentry.io/1")


def test_sentry_valid_dsn():
    fake = MagicMock()
    with patch.dict("sys.modules", {"sentry_sdk": fake}):
        init_sentry("https://abc@sentry.io/1")
    fake.init.assert_called_once_with(dsn="https://abc@sentry.io/1")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_retry_middleware_retries_then_succeeds():
    from aiogram.exceptions import TelegramRetryAfter

    calls = {"n": 0}

    async def flaky(event, data):
        calls["n"] += 1
        if calls["n"] < 2:
            raise TelegramRetryAfter(None, "r", 0)
        return "done"

    mw = RetryMiddleware(max_retries=3, delay=0)
    with patch("src.core.errors.asyncio.sleep", new=AsyncMock()):
        result = await mw(flaky, "ev", {})
    assert result == "done"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_retry_middleware_gives_up():
    from aiogram.exceptions import TelegramNetworkError

    async def always_fail(event, data):
        raise TelegramNetworkError(None, "n")

    mw = RetryMiddleware(max_retries=2, delay=0)
    with patch("src.core.errors.asyncio.sleep", new=AsyncMock()), pytest.raises(TelegramNetworkError):
        await mw(always_fail, "ev", {})


@pytest.mark.asyncio
async def test_default_error_handler_types():
    from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

    with patch("src.core.errors.asyncio.sleep", new=AsyncMock()):
        await default_error_handler("ev", TelegramRetryAfter(None, "r", 0))
        await default_error_handler("ev", TelegramNetworkError(None, "n"))
        await default_error_handler("ev", RuntimeError("boom"))


def test_register_error_handler_uses_decorator():
    fake_dp = MagicMock()
    fake_dp.error = MagicMock(return_value=MagicMock())
    register_error_handler(fake_dp)
    fake_dp.error.assert_called_once()


# --------------------------------------------------------------------------- #
# FSM states
# --------------------------------------------------------------------------- #
def test_fsm_states_are_statesgroups():
    from aiogram.fsm.state import StatesGroup

    for group in (ItemAdd, ItemEdit, AdminAuth):
        assert issubclass(group, StatesGroup)
    assert ItemAdd.entering_sku is not None
    assert AdminAuth.waiting_password is not None


# --------------------------------------------------------------------------- #
# Nav
# --------------------------------------------------------------------------- #
def test_nav_menus_return_keyboards():
    cm = client_menu()
    am = admin_menu()
    assert cm.keyboard
    assert am.keyboard
    assert len(cm.keyboard) >= 2
    assert len(am.keyboard) >= 2


# --------------------------------------------------------------------------- #
# Auth middleware
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_auth_middleware_injects_db():
    db = MagicMock()
    mw = AuthMiddleware(db)
    handler = AsyncMock(return_value="x")
    data: dict = {}
    assert await mw(handler, "ev", data) == "x"
    assert data["db"] is db


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_payments_mock_provider():
    assert issubclass(MockPaymentProvider, PaymentProvider)
    p = MockPaymentProvider()
    pid = await p.create_payment(title="t", description="d", payload="p", amount=100)
    assert isinstance(pid, str)
    assert await p.check_payment(pid) is True


# --------------------------------------------------------------------------- #
# Handlers (pricesentry + admin)
# --------------------------------------------------------------------------- #
def _make_bot():
    bot = Bot("123456789:AAfake")
    bot.session.make_request = AsyncMock()
    return bot


def _make_message(bot, text, uid=1):
    user = User(id=uid, is_bot=False, first_name="U")
    msg = Message(
        message_id=1,
        chat=Chat(id=uid, type="private"),
        date=datetime.now(),
        from_user=user,
        text=text,
    )
    return msg.as_(bot)


def _make_callback(bot, data, uid=1):
    user = User(id=uid, is_bot=False, first_name="U")
    msg = Message(
        message_id=2, chat=Chat(id=uid, type="private"), date=datetime.now(), from_user=user
    ).as_(bot)
    cb = CallbackQuery(id="1", from_user=user, chat_instance="ci", message=msg, data=data)
    return cb.as_(bot)


def _handler(router, name):
    for obs in (router.message, router.callback_query):
        for hi in obs.handlers:
            if getattr(hi.callback, "__name__", None) == name:
                return hi.callback
    raise AssertionError(f"handler {name} not found")


@pytest.fixture
async def pricesentry_state():
    cfg = Config(bot_token="123456789:AAfake", admin_ids=[1], db_path=":memory:")
    with patch("src.core.bot_factory.RedisStorage.from_url", return_value=MemoryStorage()):
        state = AppState(cfg)
    from src.core.migrations import migrate

    await migrate(state.db)
    yield state
    await state.db.close()


@pytest.fixture
async def admin_state():
    cfg = Config(bot_token="123456789:AAfake", admin_ids=[1], db_path=":memory:")
    with patch("src.core.bot_factory.RedisStorage.from_url", return_value=MemoryStorage()):
        state = AppState(cfg)
    from src.core.migrations import migrate

    await migrate(state.db)
    yield state
    await state.db.close()


@pytest.mark.asyncio
async def test_pricesentry_start_and_add_flow(pricesentry_state):
    bot = _make_bot()
    pricesentry_state.bot = bot
    router = create_pricesentry_router(pricesentry_state)
    storage = MemoryStorage()
    key = StorageKey(chat_id=1, user_id=1, bot_id=0, business_connection_id=None)

    await _handler(router, "cmd_start")(_make_message(bot, "/start"))
    await _handler(router, "start_add")(_make_message(bot, "add"), state=FSMContext(storage, key))
    await _handler(router, "enter_sku")(_make_message(bot, "SKU1"), state=FSMContext(storage, key))
    await _handler(router, "choose_marketplace")(_make_callback(bot, "mp:wb"), state=FSMContext(storage, key))
    await _handler(router, "enter_name")(_make_message(bot, "Name"), state=FSMContext(storage, key))
    await _handler(router, "enter_target_price")(_make_message(bot, "90.5"), state=FSMContext(storage, key))
    await _handler(router, "enter_url")(_make_message(bot, "http://example.com/x"), state=FSMContext(storage, key))
    await _handler(router, "confirm_add")(_make_callback(bot, "item_confirm"), state=FSMContext(storage, key))

    from src.pricesentry import service

    items = await service.get_user_items(pricesentry_state.db, 1)
    assert len(items) == 1
    await _handler(router, "my_items")(_make_message(bot, "my"))
    await _handler(router, "stats")(_make_message(bot, "stats"))


@pytest.mark.asyncio
async def test_pricesentry_cancel_and_alerts(pricesentry_state):
    bot = _make_bot()
    pricesentry_state.bot = bot
    router = create_pricesentry_router(pricesentry_state)
    storage = MemoryStorage()
    key = StorageKey(chat_id=1, user_id=1, bot_id=0, business_connection_id=None)
    await _handler(router, "start_add")(_make_message(bot, "add"), state=FSMContext(storage, key))
    await _handler(router, "cancel_add")(_make_callback(bot, "item_cancel"), state=FSMContext(storage, key))
    await _handler(router, "my_alerts")(_make_message(bot, "alerts"))


@pytest.mark.asyncio
async def test_admin_non_admin_early_returns(admin_state):
    bot = _make_bot()
    admin_state.bot = bot
    router = create_admin_router(admin_state)
    msg = _make_message(bot, "admin", uid=99)
    before = bot.session.make_request.await_count
    await _handler(router, "admin_stats")(msg)
    await _handler(router, "admin_check_prices")(msg)
    assert bot.session.make_request.await_count == before


@pytest.mark.asyncio
async def test_admin_stats_as_admin(admin_state):
    bot = _make_bot()
    admin_state.bot = bot
    router = create_admin_router(admin_state)
    msg = _make_message(bot, "admin", uid=1)
    before = bot.session.make_request.await_count
    await _handler(router, "admin_stats")(msg)
    assert bot.session.make_request.await_count >= before + 1


# --------------------------------------------------------------------------- #
# Scheduler loop
# --------------------------------------------------------------------------- #
class _BreakLoop(Exception):
    pass


@pytest.mark.asyncio
async def test_price_check_loop_empty_then_break():
    fake_bot = MagicMock()
    fake_bot.send_message = AsyncMock()
    with patch("src.scheduler.loop.service.get_all_active_items", new=AsyncMock(return_value=[])), \
         patch("src.scheduler.loop.asyncio.sleep", side_effect=_BreakLoop), pytest.raises(_BreakLoop):
        await price_check_loop(fake_bot, MagicMock(), interval=10)


@pytest.mark.asyncio
async def test_price_check_loop_processes_item_and_alerts():
    fake_bot = MagicMock()
    fake_bot.send_message = AsyncMock()
    item = {
        "id": 7,
        "owner_id": 1,
        "url": None,
        "current_price": 10,
        "target_price": 5,
        "name": "Widget",
    }
    with patch("src.scheduler.loop.service.get_all_active_items", new=AsyncMock(return_value=[item])), \
         patch("src.scheduler.loop._fresh_price", new=AsyncMock(return_value=3.0)), \
         patch("src.scheduler.loop.service.record_price", new=AsyncMock()), \
         patch("src.scheduler.loop.service.create_alert", new=AsyncMock()), \
         patch("src.scheduler.loop.service.update_item_price", new=AsyncMock()), \
         patch("src.scheduler.loop.asyncio.sleep", side_effect=_BreakLoop), pytest.raises(_BreakLoop):
        await price_check_loop(fake_bot, MagicMock(), interval=10)
    fake_bot.send_message.assert_awaited()
