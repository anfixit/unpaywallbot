"""Middleware для ограничения частоты запросов.

Защищает бота от DOS-атак и чрезмерного использования.
Использует Redis для распределённого ограничения.
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
from bot.storage.redis_client import redis_client

__all__ = ['RateLimiterMiddleware']


class RateLimiterMiddleware(BaseMiddleware):
    """Ограничивает количество запросов от пользователя.

    Лимиты:
    - Не более N сообщений в минуту
    - Не более N сообщений в час
    - Не более N сообщений в день
    """

    def __init__(
        self,
        rate_per_minute: int = 10,
        rate_per_hour: int = 30,
        rate_per_day: int = 100,
    ) -> None:
        """Инициализировать middleware.

        Args:
            rate_per_minute: Макс. сообщений в минуту.
            rate_per_hour: Макс. сообщений в час.
            rate_per_day: Макс. сообщений в день.
        """
        self.rate_per_minute = rate_per_minute
        self.rate_per_hour = rate_per_hour
        self.rate_per_day = rate_per_day
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
        """Обработать событие с проверкой лимитов."""
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        # Пропускаем админов
        admin_ids = getattr(settings, 'admin_ids', [])
        if user_id in admin_ids:
            return await handler(event, data)

        is_allowed, error_msg = await self._check_limits(
            user_id,
        )

        if not is_allowed:
            if isinstance(event, Message):
                await event.answer(f'⏳ {error_msg}')
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    error_msg, show_alert=True,
                )
            return None

        await self._increment_counters(user_id)
        return await handler(event, data)

    async def _check_limits(
        self,
        user_id: int,
    ) -> tuple[bool, str]:
        """Проверить, не превысил ли пользователь лимиты.

        Returns:
            (разрешено, сообщение_об_ошибке).
        """
        client = redis_client.client

        minute_key = f'rate:minute:{user_id}'
        hour_key = f'rate:hour:{user_id}'
        day_key = f'rate:day:{user_id}'

        minute_count = int(
            await client.get(minute_key) or 0,
        )
        hour_count = int(
            await client.get(hour_key) or 0,
        )
        day_count = int(
            await client.get(day_key) or 0,
        )

        if minute_count >= self.rate_per_minute:
            return (
                False,
                'Слишком много запросов в минуту. '
                'Подожди немного.',
            )

        if hour_count >= self.rate_per_hour:
            return (
                False,
                'Достигнут часовой лимит запросов. '
                'Попробуй позже.',
            )

        if day_count >= self.rate_per_day:
            return (
                False,
                'Достигнут дневной лимит. '
                'Возвращайся завтра.',
            )

        return True, ''

    async def _increment_counters(
        self,
        user_id: int,
    ) -> None:
        """Увеличить счётчики запросов."""
        client = redis_client.client

        minute_key = f'rate:minute:{user_id}'
        hour_key = f'rate:hour:{user_id}'
        day_key = f'rate:day:{user_id}'

        pipe = client.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)

        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)

        pipe.incr(day_key)
        pipe.expire(day_key, 86400)

        await pipe.execute()
