"""Кеширование и хранение данных.

Содержит:
- redis_client — подключение к Redis (lazy singleton)
- cache — функции кеширования статей
"""

from bot.storage.cache import (
    get_cache_stats,
    get_cached_article,
    invalidate_article_cache,
    save_article_to_cache,
)
from bot.storage.redis_client import (
    RedisClient,
    get_redis_client,
)

__all__ = [
    'RedisClient',
    'get_cached_article',
    'get_cache_stats',
    'get_redis_client',
    'invalidate_article_cache',
    'save_article_to_cache',
]
