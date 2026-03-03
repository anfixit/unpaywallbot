"""Протоколы для структурной типизации.

Protocol (PEP 544) — duck typing с проверкой mypy.
Платформы не наследуют BasePlatform, а просто
реализуют нужный интерфейс. mypy проверяет
совместимость статически.
"""

from typing import Protocol, runtime_checkable

from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo

__all__ = ['PlatformProtocol']


@runtime_checkable
class PlatformProtocol(Protocol):
    """Интерфейс платформенного обработчика.

    Любой класс с методом ``handle`` подходящей
    сигнатуры считается совместимым — явное
    наследование не требуется.

    Example::

        class MyPlatform:
            async def handle(
                self, url, paywall_info, *,
                user_id=None,
            ) -> Article | None:
                ...

        # mypy: OK, структурно совместим
        p: PlatformProtocol = MyPlatform()
    """

    async def handle(
        self,
        url: str,
        paywall_info: PaywallInfo,
        *,
        user_id: int | None = None,
    ) -> Article | None:
        """Обработать URL и вернуть статью.

        Args:
            url: URL статьи.
            paywall_info: Результат классификации.
            user_id: ID пользователя Telegram.

        Returns:
            Article или None при неудаче.
        """
        ...
