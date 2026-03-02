"""Клиент для подключения к Redis.

Обеспечивает единое подключение к Redis с повторными попытками
при временных ошибках и graceful shutdown.
"""

import asyncio

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from bot.config import settings
from bot.constants import (
    MAX_RETRY_COUNT,
    RETRY_BACKOFF_FACTOR,
)

__all__ = ['RedisClient']


class RedisClient:
    """Асинхронный клиент Redis с повторными попытками.

    Пример использования:
        redis = RedisClient()
        await redis.connect()
        await redis.set('key', 'value')
        value = await redis.get('key')
        await redis.close()
    """

    def __init__(
        self,
        redis_url: str | None = None,
        max_retries: int = MAX_RETRY_COUNT,
        retry_backoff: int = RETRY_BACKOFF_FACTOR,
    ) -> None:
        """Инициализировать клиент Redis.

        Args:
            redis_url: URL подключения к Redis (если None, берётся из settings).
            max_retries: Максимальное количество повторных попыток.
            retry_backoff: Коэффициент увеличения задержки между попытками.
        """
        self.redis_url = redis_url or settings.redis_url
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._redis: Redis | None = None
        self._pool: ConnectionPool | None = None

    async def connect(self) -> None:
        """Установить соединение с Redis.

        Raises:
            RedisError: Если не удалось подключиться после всех попыток.
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                self._pool = ConnectionPool.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=10,
                )
                self._redis = Redis(connection_pool=self._pool)

                # Проверяем соединение
                await self._redis.ping()
                return

            except RedisConnectionError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff ** attempt
                    await asyncio.sleep(wait_time)
                continue

        raise RedisError(f'Не удалось подключиться к Redis после {self.max_retries} попыток: {last_error}')

    async def close(self) -> None:
        """Закрыть соединение с Redis."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

        if self._pool:
            await self._pool.aclose()
            self._pool = None

    @property
    def client(self) -> Redis:
        """Получить клиент Redis.

        Raises:
            RuntimeError: Если клиент не подключён.
        """
        if not self._redis:
            raise RuntimeError('Redis клиент не подключён. Вызовите connect() сначала.')
        return self._redis

    async def __aenter__(self) -> 'RedisClient':
        """Вход в контекстный менеджер."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Выход из контекстного менеджера."""
        await self.close()


# Синглтон для использования во всём приложении
redis_client = RedisClient()
