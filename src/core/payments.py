from __future__ import annotations

from abc import ABC, abstractmethod


class PaymentProvider(ABC):
    @abstractmethod
    async def create_payment(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "RUB"
    ) -> str:
        ...

    @abstractmethod
    async def check_payment(self, payment_id: str) -> bool:
        ...


class MockPaymentProvider(PaymentProvider):
    async def create_payment(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "RUB"
    ) -> str:
        return "mock_payment_123"

    async def check_payment(self, payment_id: str) -> bool:
        return True
