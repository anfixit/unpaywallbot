"""Atomic Redis rate limiting middleware."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    Message,
    TelegramObject,
)
from redis.exceptions import RedisError

from bot.storage.redis_client import get_redis_client
from bot.utils.privacy import pseudonymize_user_id

__all__ = ['RateLimiterMiddleware']

logger = logging.getLogger(__name__)

_TTL_MINUTE = 60
_TTL_HOUR = 3600
_TTL_DAY = 86400

_RATE_LIMIT_SCRIPT = """
for index = 1, 3 do
    local current = tonumber(redis.call('GET', KEYS[index]) or '0')
    local limit = tonumber(ARGV[index])
    if current >= limit then
        return index
    end
end

for index = 1, 3 do
    local value = redis.call('INCR', KEYS[index])
    if value == 1 then
        redis.call('EXPIRE', KEYS[index], ARGV[index + 3])
    end
end

return 0
"""


class RateLimiterMiddleware(BaseMiddleware):
    """Apply minute, hour and day limits atomically."""

    def __init__(
        self,
        rate_per_minute: int = 10,
        rate_per_hour: int = 30,
        rate_per_day: int = 100,
    ) -> None:
        """Configure limits."""
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
        """Check and increment counters in one Redis operation."""
        user = getattr(event, 'from_user', None)
        if user is None:
            return await handler(event, data)

        user_hash = pseudonymize_user_id(user.id)
        try:
            blocked_window = await self._consume(user.id)
        except (RedisError, RuntimeError):
            logger.exception(
                'Rate limiter unavailable for user=%s',
                user_hash,
            )
            await self._reply(
                event,
                'Сервис временно недоступен. Попробуй позже.',
            )
            return None

        if blocked_window:
            message = {
                1: 'Слишком много запросов в минуту. Подожди немного.',
                2: 'Достигнут часовой лимит. Попробуй позже.',
                3: 'Достигнут дневной лимит. Возвращайся завтра.',
            }[blocked_window]
            logger.info(
                'Rate limit user=%s window=%d',
                user_hash,
                blocked_window,
            )
            await self._reply(event, message)
            return None

        return await handler(event, data)

    async def _consume(self, user_id: int) -> int:
        """Return blocked window number or zero."""
        client = get_redis_client().client
        operation = cast(
            Awaitable[object],
            client.eval(
                _RATE_LIMIT_SCRIPT,
                3,
                f'rate:minute:{user_id}',
                f'rate:hour:{user_id}',
                f'rate:day:{user_id}',
                self.rate_per_minute,
                self.rate_per_hour,
                self.rate_per_day,
                _TTL_MINUTE,
                _TTL_HOUR,
                _TTL_DAY,
            ),
        )
        result = await operation
        return int(cast(int | str, result))

    @staticmethod
    async def _reply(
        event: TelegramObject,
        message: str,
    ) -> None:
        """Reply to a blocked update."""
        if isinstance(event, Message):
            await event.answer(f'⏳ {message}')
        elif isinstance(event, CallbackQuery):
            await event.answer(
                message,
                show_alert=True,
            )
