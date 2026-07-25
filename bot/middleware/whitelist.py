"""Middleware контроля доступа к Telegram-боту."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    Message,
    TelegramObject,
)

from bot.config import settings

__all__ = ['WhitelistMiddleware']


class WhitelistMiddleware(BaseMiddleware):
    """Разрешить public mode или пользователей из allowlist."""

    def __init__(
        self,
        whitelist: list[int] | None = None,
        *,
        public_access: bool | None = None,
    ) -> None:
        """Инициализировать политику доступа."""
        values = (
            settings.allowed_users
            if whitelist is None
            else whitelist
        )
        self.whitelist = frozenset(values)
        self.public_access = (
            settings.public_access
            if public_access is None
            else public_access
        )
        super().__init__()

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Проверить доступ пользователя."""
        if self.public_access:
            return await handler(event, data)

        user = getattr(event, 'from_user', None)
        user_id = user.id if user else None

        if user_id is not None and user_id in self.whitelist:
            return await handler(event, data)

        if not settings.is_production and not self.whitelist:
            return await handler(event, data)

        await self._deny(event)
        return None

    @staticmethod
    async def _deny(event: TelegramObject) -> None:
        """Отправить безопасный отказ в доступе."""
        if isinstance(event, Message):
            await event.answer(
                '🔒 Доступ к боту ограничен.',
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                'Доступ ограничен',
                show_alert=True,
            )
