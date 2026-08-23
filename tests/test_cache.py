"""Тесты для кеширования статей."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
)

from bot.models.article import Article
from bot.storage.cache import (
    get_cache_stats,
    get_cached_article,
    invalidate_article_cache,
    save_article_to_cache,
)


@pytest.fixture
def sample_article() -> Article:
    """Статья для тестов."""
    return Article(
        url='https://test.com/article',
        content='Test content' * 100,
        title='Test Article',
        author='Test Author',
    )


def _mock_redis_client():
    """Создать мок для get_redis_client."""
    mock_redis = AsyncMock()
    mock_redis.client = AsyncMock()
    return mock_redis


@pytest.mark.asyncio
async def test_save_and_get(
    sample_article,
) -> None:
    """Сохранение и получение из кеша."""
    mock_redis = _mock_redis_client()
    mock_redis.client.setex = AsyncMock()
    mock_redis.client.get = AsyncMock(
        return_value=None,
    )

    with patch(
        'bot.storage.cache.get_redis_client',
        return_value=mock_redis,
    ):
        result = await save_article_to_cache(
            sample_article,
        )
        assert result is True
        mock_redis.client.setex.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_cache(
    sample_article,
) -> None:
    """Удаление из кеша."""
    mock_redis = _mock_redis_client()
    mock_redis.client.delete = AsyncMock(
        return_value=1,
    )

    with patch(
        'bot.storage.cache.get_redis_client',
        return_value=mock_redis,
    ):
        result = await invalidate_article_cache(
            sample_article.url,
        )
        assert result is True
        mock_redis.client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_cache_stats() -> None:
    """Получение статистики кеша."""
    mock_redis = _mock_redis_client()

    async def scan_keys():
        for key in (
            'article:1',
            'article:2',
            'article:3',
        ):
            yield key

    mock_redis.client.scan_iter = Mock(
        return_value=scan_keys(),
    )
    mock_redis.client.info = AsyncMock(
        return_value={'used_memory': 1024},
    )

    with patch(
        'bot.storage.cache.get_redis_client',
        return_value=mock_redis,
    ):
        stats = await get_cache_stats()
        assert stats['articles_count'] == 3
        assert stats['memory_bytes'] == 1024


@pytest.mark.asyncio
async def test_save_empty_article() -> None:
    """Пустая статья не сохраняется."""
    empty = Article(url='https://test.com/empty')
    result = await save_article_to_cache(empty)
    assert result is False


@pytest.mark.asyncio
async def test_get_survives_redis_failure() -> None:
    """Недоступный Redis не ломает чтение кеша."""
    mock_redis = _mock_redis_client()
    mock_redis.client.get = AsyncMock(
        side_effect=RedisConnectionError('down'),
    )

    with patch(
        'bot.storage.cache.get_redis_client',
        return_value=mock_redis,
    ):
        result = await get_cached_article(
            'https://test.com/article',
        )

    assert result is None


@pytest.mark.asyncio
async def test_get_survives_disconnected_client() -> None:
    """Неподключённый клиент возвращает промах кеша."""
    mock_redis = Mock()
    type(mock_redis).client = property(
        lambda _self: (_ for _ in ()).throw(
            RuntimeError('не подключён'),
        ),
    )

    with patch(
        'bot.storage.cache.get_redis_client',
        return_value=mock_redis,
    ):
        result = await get_cached_article(
            'https://test.com/article',
        )

    assert result is None
