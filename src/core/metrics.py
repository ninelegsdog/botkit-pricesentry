from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

logger = logging.getLogger(__name__)

UPDATES_TOTAL = Counter(
    "bot_updates_total",
    "Total updates received from Telegram",
    ["type"],
)
PRICES_CHECKED_TOTAL = Counter(
    "bot_prices_checked_total",
    "Price checks performed",
)
ALERTS_SENT_TOTAL = Counter(
    "bot_alerts_sent_total",
    "Price alerts sent",
)
ERRORS_TOTAL = Counter(
    "bot_errors_total",
    "Total errors handled by the global error handler",
    ["error_type"],
)


class UpdatesMiddleware:
    """Counts every incoming update."""

    async def __call__(
        self,
        handler: Any,
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        UPDATES_TOTAL.labels(type=type(event).__name__.lower()).inc()
        return await handler(event, data)


@dataclass
class Metrics:
    _start: float = field(default_factory=time.time)
    messages_processed: int = 0
    prices_checked: int = 0
    alerts_sent: int = 0
    errors: int = 0

    def inc_messages(self) -> None:
        self.messages_processed += 1

    def inc_prices_checked(self) -> None:
        self.prices_checked += 1
        PRICES_CHECKED_TOTAL.inc()

    def inc_alerts_sent(self) -> None:
        self.alerts_sent += 1
        ALERTS_SENT_TOTAL.inc()

    def inc_errors(self) -> None:
        self.errors += 1
        ERRORS_TOTAL.labels(error_type="domain").inc()

    def uptime_seconds(self) -> float:
        return time.time() - self._start


async def health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def metrics(request: web.Request) -> web.Response:
    return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


def create_metrics_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/metrics", metrics)
    return app


async def start_metrics_server(port: int) -> web.AppRunner:
    runner = web.AppRunner(create_metrics_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Metrics server started on port %s", port)
    return runner
