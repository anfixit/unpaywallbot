"""Кеширование и хранение данных.

Содержит:
- redis_client - подключение к Redis
- cache - функции кеширования статей
"""

from bot.storage.cache import (
    get_cache_stats,
    get_cached_article,
    invalidate_article_cache,
    save_article_to_cache,
)
from bot.storage.redis_client import RedisClient, redis_client

__all__ = [
    'RedisClient',
    'redis_client',
    'get_cached_article',
    'save_article_to_cache',
    'invalidate_article_cache',
    'get_cache_stats',
]
