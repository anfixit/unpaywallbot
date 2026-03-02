"""Middleware для ограничения частоты запросов (rate limiting).

Защищает бота от DOS-атак и чрезмерного использования.
Использует Redis для распределённого ограничения.
"""

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from bot.storage.redis_client import redis_client
from bot.config import settings

__all__ = ['RateLimiterMiddleware']


class RateLimiterMiddleware(BaseMiddleware):
    """Ограничивает количество запросов от пользователя.

    Лимиты:
    - Не более 10 сообщений в минуту
    - Не более 30 сообщений в час
    - Не более 100 сообщений в день
    """

    def __init__(
        self,
        rate_per_minute: int = 10,
        rate_per_hour: int = 30,
        rate_per_day: int = 100,
    ) -> None:
        """Инициализировать middleware.

        Args:
            rate_per_minute: Максимум сообщений в минуту.
            rate_per_hour: Максимум сообщений в час.
            rate_per_day: Максимум сообщений в день.
        """
        self.rate_per_minute = rate_per_minute
        self.rate_per_hour = rate_per_hour
        self.rate_per_day = rate_per_day
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Обработать событие с проверкой лимитов."""
        # Определяем user_id
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        # Пропускаем админов (user_id из whitelist потом)
        if user_id in getattr(settings, 'admin_ids', []):
            return await handler(event, data)

        # Проверяем лимиты
        is_allowed, error_message = await self._check_limits(user_id)

        if not is_allowed:
            # Отвечаем в зависимости от типа события
            if isinstance(event, Message):
                await event.answer(f'⏳ {error_message}')
            elif isinstance(event, CallbackQuery):
                await event.answer(error_message, show_alert=True)
            return

        # Увеличиваем счётчики
        await self._increment_counters(user_id)

        # Передаём управление дальше
        return await handler(event, data)

    async def _check_limits(self, user_id: int) -> tuple[bool, str]:
        """Проверить, не превысил ли пользователь лимиты.

        Returns:
            (разрешено, сообщение_об_ошибке)
        """
        client = redis_client.client
        now = int(time.time())
        day_start = now - 86400  # 24 часа назад

        # Ключи для разных периодов
        minute_key = f'rate:minute:{user_id}'
        hour_key = f'rate:hour:{user_id}'
        day_key = f'rate:day:{user_id}'

        # Получаем текущие значения
        minute_count = await client.get(minute_key) or 0
        hour_count = await client.get(hour_key) or 0
        day_count = await client.get(day_key) or 0

        minute_count = int(minute_count)
        hour_count = int(hour_count)
        day_count = int(day_count)

        if minute_count >= self.rate_per_minute:
            return False, 'Слишком много запросов в минуту. Подожди немного.'

        if hour_count >= self.rate_per_hour:
            return False, 'Достигнут часовой лимит запросов. Попробуй позже.'

        if day_count >= self.rate_per_day:
            return False, 'Достигнут дневной лимит запросов. Возвращайся завтра.'

        return True, ''

    async def _increment_counters(self, user_id: int) -> None:
        """Увеличить счётчики запросов."""
        client = redis_client.client
        now = int(time.time())

        minute_key = f'rate:minute:{user_id}'
        hour_key = f'rate:hour:{user_id}'
        day_key = f'rate:day:{user_id}'

        # Инкрементим с истечением срока
        pipe = client.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)

        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)

        pipe.incr(day_key)
        pipe.expire(day_key, 86400)

        await pipe.execute()
