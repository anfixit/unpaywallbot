"""Кеширование статей в Redis.

Сохраняет извлечённые статьи, чтобы не запрашивать
сайты повторно.
"""

import json
import logging
from datetime import UTC, datetime
from typing import TypedDict

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


class CacheStats(TypedDict):
    """Статистика кеша Redis."""

    articles_count: int
    memory_bytes: int
    memory_mb: float


def _article_key(url_hash: str) -> str:
    """Сформировать Redis-ключ для статьи."""
    return f'{_KEY_PREFIX}:{url_hash}'


def _optional_text(value: object) -> str | None:
    """Вернуть строку или None для необязательного поля."""
    return value if isinstance(value, str) else None


def _parse_datetime(value: object) -> datetime | None:
    """Преобразовать ISO-строку в timezone-aware datetime."""
    if not isinstance(value, str) or not value:
        return None

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _deserialize_article(payload: object) -> Article | None:
    """Проверить JSON кеша и восстановить Article."""
    if not isinstance(payload, dict):
        return None

    raw_url = payload.get('url')
    raw_content = payload.get('content', '')
    if not isinstance(raw_url, str):
        return None
    if not isinstance(raw_content, str):
        return None

    extracted_at = _parse_datetime(payload.get('extracted_at'))
    if extracted_at is None:
        extracted_at = datetime.now(UTC)

    return Article(
        url=raw_url,
        content=raw_content,
        title=_optional_text(payload.get('title')),
        author=_optional_text(payload.get('author')),
        published_at=_parse_datetime(payload.get('published_at')),
        extracted_at=extracted_at,
        paywall_type=_optional_text(payload.get('paywall_type')),
        extraction_method=_optional_text(
            payload.get('extraction_method'),
        ),
    )


async def get_cached_article(url: str) -> Article | None:
    """Получить статью из кеша по URL."""
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
        payload = json.loads(data)
        return _deserialize_article(payload)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning(
            'Ошибка десериализации кеша для %s: %s',
            url_hash[:12],
            exc,
        )
        return None


async def save_article_to_cache(
    article: Article,
    ttl: int = CACHE_TTL_LONG,
) -> bool:
    """Сохранить статью в кеш."""
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
            json.dumps(article_dict, ensure_ascii=False),
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


def _serialize_article(article: Article) -> dict[str, object]:
    """Конвертировать Article в JSON-совместимый словарь."""
    published_at = article.published_at
    return {
        'url': article.url,
        'content': article.content,
        'title': article.title,
        'author': article.author,
        'published_at': (
            published_at.isoformat() if published_at else None
        ),
        'extracted_at': article.extracted_at.isoformat(),
        'paywall_type': article.paywall_type,
        'extraction_method': article.extraction_method,
    }


async def invalidate_article_cache(url: str) -> bool:
    """Удалить статью из кеша."""
    url_hash = get_url_hash(url)
    if not url_hash:
        return False

    try:
        client = get_redis_client().client
        await client.delete(_article_key(url_hash))
        return True
    except (RedisError, RuntimeError) as exc:
        logger.warning(
            'Ошибка удаления кеша: %s - %s',
            url_hash[:12],
            exc,
        )
        return False


async def get_cache_stats() -> CacheStats:
    """Получить статистику использования кеша."""
    try:
        client = get_redis_client().client
        articles_count = 0
        async for _key in client.scan_iter(
            match=f'{_KEY_PREFIX}:*',
            count=100,
        ):
            articles_count += 1

        info = await client.info('memory')
        raw_memory = info.get('used_memory', 0)
        memory_bytes = (
            raw_memory if isinstance(raw_memory, int) else 0
        )
        return {
            'articles_count': articles_count,
            'memory_bytes': memory_bytes,
            'memory_mb': round(memory_bytes / 1024 / 1024, 2),
        }
    except (RedisError, RuntimeError) as exc:
        logger.warning('Ошибка получения статистики: %s', exc)
        return {
            'articles_count': 0,
            'memory_bytes': 0,
            'memory_mb': 0.0,
        }
