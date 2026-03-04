"""Кеширование статей в Redis.

Сохраняет извлечённые статьи, чтобы не долбить
сайты повторно.
Ключи: ``article:{url_hash}`` → JSON с данными статьи.
"""

import json
import logging
from datetime import UTC, datetime

from redis.exceptions import RedisError

from bot.constants import CACHE_TTL_LONG
from bot.models.article import Article
from bot.storage.redis_client import get_redis_client
from bot.utils.url_utils import get_url_hash

__all__ = [
    'get_cache_stats',
    'get_cached_article',
    'invalidate_article_cache',
    'save_article_to_cache',
]

logger = logging.getLogger(__name__)

_KEY_PREFIX = 'article'


def _article_key(url_hash: str) -> str:
    """Сформировать Redis-ключ для статьи."""
    return f'{_KEY_PREFIX}:{url_hash}'


async def get_cached_article(
    url: str,
) -> Article | None:
    """Получить статью из кеша по URL.

    Args:
        url: URL статьи.

    Returns:
        Article или None, если нет в кеше.
    """
    url_hash = get_url_hash(url)
    if not url_hash:
        return None

    try:
        client = get_redis_client().client
    except RuntimeError:
        return None

    data = await client.get(_article_key(url_hash))
    if not data:
        return None

    try:
        article_dict = json.loads(data)
        _restore_datetime(article_dict)
        return Article(**article_dict)
    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        logger.warning(
            'Ошибка десериализации кеша'
            ' для %s: %s',
            url_hash[:12],
            exc,
        )
        return None


def _restore_datetime(
    article_dict: dict,
) -> None:
    """Конвертировать ISO-строки в datetime.

    Гарантирует timezone-aware результат (UTC).
    """
    for field in ('extracted_at', 'published_at'):
        raw = article_dict.get(field)
        if not raw:
            continue
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        article_dict[field] = dt


async def save_article_to_cache(
    article: Article,
    ttl: int = CACHE_TTL_LONG,
) -> bool:
    """Сохранить статью в кеш.

    Args:
        article: Статья для сохранения.
        ttl: Время жизни в секундах.

    Returns:
        True если сохранили, False если ошибка.
    """
    if article.is_empty:
        return False

    url_hash = get_url_hash(article.url)
    if not url_hash:
        return False

    try:
        article_dict = _serialize_article(article)
        client = get_redis_client().client

        await client.setex(
            _article_key(url_hash),
            ttl,
            json.dumps(
                article_dict, ensure_ascii=False,
            ),
        )
        return True
    except (TypeError, ValueError) as exc:
        logger.warning(
            'Ошибка сериализации статьи %s: %s',
            url_hash[:12],
            exc,
        )
        return False
    except (RedisError, RuntimeError) as exc:
        logger.warning(
            'Ошибка записи в Redis %s: %s',
            url_hash[:12],
            exc,
        )
        return False


def _serialize_article(
    article: Article,
) -> dict:
    """Конвертировать Article в dict для JSON."""
    pub_at = article.published_at
    return {
        'url': article.url,
        'content': article.content,
        'title': article.title,
        'author': article.author,
        'published_at': (
            pub_at.isoformat()
            if pub_at
            else None
        ),
        'extracted_at': (
            article.extracted_at.isoformat()
        ),
        'paywall_type': article.paywall_type,
        'extraction_method': (
            article.extraction_method
        ),
    }


async def invalidate_article_cache(
    url: str,
) -> bool:
    """Удалить статью из кеша.

    Args:
        url: URL статьи.

    Returns:
        True если удалили или ключа не было.
    """
    url_hash = get_url_hash(url)
    if not url_hash:
        return False

    try:
        client = get_redis_client().client
        await client.delete(
            _article_key(url_hash),
        )
        return True
    except (RedisError, RuntimeError) as exc:
        logger.warning(
            'Ошибка удаления кеша: %s — %s',
            url_hash[:12],
            exc,
        )
        return False


async def get_cache_stats() -> dict[str, int]:
    """Получить статистику использования кеша.

    Returns:
        Словарь с количеством ключей и памятью.
    """
    try:
        client = get_redis_client().client

        keys = await client.keys(
            f'{_KEY_PREFIX}:*',
        )
        count = len(keys)

        info = await client.info('memory')
        memory_bytes = info.get('used_memory', 0)

        return {
            'articles_count': count,
            'memory_bytes': memory_bytes,
            'memory_mb': round(
                memory_bytes / 1024 / 1024, 2,
            ),
        }
    except (RedisError, RuntimeError) as exc:
        logger.warning(
            'Ошибка получения статистики: %s', exc,
        )
        return {
            'articles_count': 0,
            'memory_bytes': 0,
            'memory_mb': 0,
        }
