"""Middleware для ограничения доступа по белому списку.

Полезно для тестирования и защиты бота от посторонних.
"""

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
    """Пропускает только пользователей из whitelist."""

    def __init__(
        self,
        whitelist: list[int] | None = None,
    ) -> None:
        """Инициализировать middleware.

        Args:
            whitelist: Разрешённые user_id.
                Если None — из settings.allowed_users.
        """
        self.whitelist = (
            whitelist or settings.allowed_users
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
        """Проверить пользователя по whitelist."""
        if not self.whitelist:
            return await handler(event, data)

        user_id = None
        if isinstance(
            event, (Message, CallbackQuery),
        ):
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        if user_id in self.whitelist:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(
                '🔒 Бот в режиме тестирования.\n'
                'Доступ только для разработчиков.',
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                'Доступ ограничен',
                show_alert=True,
            )

        return None
