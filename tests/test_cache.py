"""Тесты для кеширования статей."""

from unittest.mock import AsyncMock, patch

import pytest

from bot.models.article import Article
from bot.storage.cache import (
    get_cache_stats,
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
    mock_redis.client.keys = AsyncMock(
        return_value=[
            'article:1',
            'article:2',
            'article:3',
        ],
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
