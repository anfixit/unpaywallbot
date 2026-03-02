"""Кеширование статей в Redis.

Сохраняет извлечённые статьи, чтобы не долбить сайты повторно.
Ключи: article:{url_hash} -> JSON с данными статьи.
"""

import json
from datetime import datetime

from bot.constants import CACHE_TTL_LONG
from bot.models.article import Article
from bot.storage.redis_client import redis_client
from bot.utils.url_utils import get_url_hash

__all__ = [
    'get_cached_article',
    'save_article_to_cache',
    'invalidate_article_cache',
    'get_cache_stats',
]


async def get_cached_article(url: str) -> Article | None:
    """Получить статью из кеша по URL.

    Args:
        url: URL статьи.

    Returns:
        Article или None, если статьи нет в кеше.
    """
    url_hash = get_url_hash(url)
    if not url_hash:
        return None

    client = redis_client.client
    data = await client.get(f'article:{url_hash}')

    if not data:
        return None

    try:
        article_dict = json.loads(data)

        # Конвертируем строку обратно в datetime
        if 'extracted_at' in article_dict:
            article_dict['extracted_at'] = datetime.fromisoformat(article_dict['extracted_at'])

        return Article(**article_dict)

    except (json.JSONDecodeError, TypeError, ValueError):
        # Логирование будет в вызывающем коде
        return None


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
        # Конвертируем в dict для JSON
        article_dict = {
            'url': article.url,
            'content': article.content,
            'title': article.title,
            'author': article.author,
            'published_at': article.published_at.isoformat() if article.published_at else None,
            'extracted_at': article.extracted_at.isoformat(),
            'paywall_type': article.paywall_type,
            'extraction_method': article.extraction_method,
        }

        client = redis_client.client
        await client.setex(
            f'article:{url_hash}',
            ttl,
            json.dumps(article_dict, ensure_ascii=False),
        )
        return True

    except (TypeError, ValueError):
        return False


async def invalidate_article_cache(url: str) -> bool:
    """Удалить статью из кеша.

    Args:
        url: URL статьи.

    Returns:
        True если удалили или ключа не было, False при ошибке.
    """
    url_hash = get_url_hash(url)
    if not url_hash:
        return False

    try:
        client = redis_client.client
        await client.delete(f'article:{url_hash}')
        return True

    except Exception:
        return False


async def get_cache_stats() -> dict[str, int]:
    """Получить статистику использования кеша.

    Returns:
        Словарь с количеством ключей и занимаемой памятью.
    """
    client = redis_client.client

    try:
        # Количество ключей articles
        keys = await client.keys('article:*')
        count = len(keys)

        # Информация о памяти (если есть доступ)
        info = await client.info('memory')
        memory_bytes = info.get('used_memory', 0)

        return {
            'articles_count': count,
            'memory_bytes': memory_bytes,
            'memory_mb': round(memory_bytes / 1024 / 1024, 2),
        }

    except Exception:
        return {
            'articles_count': 0,
            'memory_bytes': 0,
            'memory_mb': 0,
        }
