from __future__ import annotations

import time
from dataclasses import dataclass, field


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

    def inc_alerts_sent(self) -> None:
        self.alerts_sent += 1

    def inc_errors(self) -> None:
        self.errors += 1

    def uptime_seconds(self) -> float:
        return time.time() - self._start
