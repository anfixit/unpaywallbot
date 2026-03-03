"""Клиент для подключения к Redis.

Обеспечивает единое подключение к Redis с повторными
попытками при временных ошибках и graceful shutdown.
"""

import asyncio
import logging

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
)
from redis.exceptions import RedisError

from bot.constants import (
    MAX_RETRY_COUNT,
    RETRY_BACKOFF_FACTOR,
)

__all__ = ['RedisClient', 'get_redis_client']

logger = logging.getLogger(__name__)

_MAX_POOL_CONNECTIONS = 10


class RedisClient:
    """Асинхронный клиент Redis с повторными попытками.

    Пример использования::

        async with RedisClient(url) as redis:
            client = redis.client
            await client.set('key', 'value')
    """

    def __init__(
        self,
        redis_url: str,
        max_retries: int = MAX_RETRY_COUNT,
        retry_backoff: int = RETRY_BACKOFF_FACTOR,
    ) -> None:
        """Инициализировать клиент Redis.

        Args:
            redis_url: URL подключения к Redis.
            max_retries: Макс. повторных попыток.
            retry_backoff: Коэффициент задержки.
        """
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._redis: Redis | None = None
        self._pool: ConnectionPool | None = None

    async def connect(self) -> None:
        """Установить соединение с Redis.

        Raises:
            RedisError: Не удалось подключиться
                после всех попыток.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                self._pool = ConnectionPool.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=_MAX_POOL_CONNECTIONS,
                )
                self._redis = Redis(
                    connection_pool=self._pool,
                )
                await self._redis.ping()
                logger.info('Redis подключён')
                return

            except RedisConnectionError as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    wait = (
                        self.retry_backoff ** attempt
                    )
                    logger.warning(
                        'Redis попытка %d/%d не '
                        'удалась, повтор через %ds',
                        attempt + 1,
                        self.max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)

        msg = (
            'Не удалось подключиться к Redis '
            f'после {self.max_retries} попыток: '
            f'{last_error}'
        )
        raise RedisError(msg)

    async def close(self) -> None:
        """Закрыть соединение с Redis."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

        if self._pool:
            await self._pool.aclose()
            self._pool = None

        logger.info('Redis соединение закрыто')

    @property
    def client(self) -> Redis:
        """Получить клиент Redis.

        Raises:
            RuntimeError: Если клиент не подключён.
        """
        if not self._redis:
            msg = (
                'Redis клиент не подключён. '
                'Вызовите connect() сначала.'
            )
            raise RuntimeError(msg)
        return self._redis

    async def __aenter__(self) -> 'RedisClient':
        """Вход в контекстный менеджер."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Выход из контекстного менеджера."""
        await self.close()


# --- Lazy singleton (§21.5) ---

_redis_client: RedisClient | None = None


def get_redis_client() -> RedisClient:
    """Получить или создать синглтон RedisClient.

    Ленивая инициализация — settings читается
    только при первом вызове, не при импорте.

    Returns:
        Экземпляр RedisClient.
    """
    global _redis_client  # noqa: PLW0603

    if _redis_client is None:
        from bot.config import settings

        _redis_client = RedisClient(
            redis_url=settings.redis_url,
        )

    return _redis_client
