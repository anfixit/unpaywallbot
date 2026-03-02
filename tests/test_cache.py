"""Тесты для кеширования статей."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from bot.models.article import Article
from bot.storage.cache import (
    get_cache_stats,
    get_cached_article,
    invalidate_article_cache,
    save_article_to_cache,
)


@pytest.fixture
def sample_article():
    """Тестовая статья."""
    return Article(
        url='https://test.com/article',
        content='Test content',
        title='Test Title',
        author='John Doe',
        published_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_save_and_get_article(sample_article):
    """Сохранить и потом получить статью."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=json.dumps({
        'url': sample_article.url,
        'content': sample_article.content,
        'title': sample_article.title,
        'author': sample_article.author,
        'published_at': sample_article.published_at.isoformat() if sample_article.published_at else None,
        'extracted_at': sample_article.extracted_at.isoformat(),
        'paywall_type': sample_article.paywall_type,
        'extraction_method': sample_article.extraction_method,
    }))

    with patch('bot.storage.cache.redis_client.client', mock_redis):
        # Сохраняем
        saved = await save_article_to_cache(sample_article)
        assert saved is True

        # Получаем
        cached = await get_cached_article(sample_article.url)
        assert cached is not None
        assert cached.url == sample_article.url
        assert cached.content == sample_article.content
        assert cached.title == sample_article.title


@pytest.mark.asyncio
async def test_get_nonexistent_article():
    """Запрос отсутствующей статьи возвращает None."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch('bot.storage.cache.redis_client.client', mock_redis):
        cached = await get_cached_article('https://test.com/nonexistent')
        assert cached is None


@pytest.mark.asyncio
async def test_invalidate_article(sample_article):
    """Удаление статьи из кеша."""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(return_value=1)

    with patch('bot.storage.cache.redis_client.client', mock_redis):
        result = await invalidate_article_cache(sample_article.url)
        assert result is True
        mock_redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_cache_stats():
    """Получение статистики кеша."""
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=['article:1', 'article:2', 'article:3'])
    mock_redis.info = AsyncMock(return_value={'used_memory': 1024})

    with patch('bot.storage.cache.redis_client.client', mock_redis):
        stats = await get_cache_stats()
        assert stats['articles_count'] == 3
        assert stats['memory_bytes'] == 1024
        assert stats['memory_mb'] == 0.0  # 1024 / 1024 / 1024


@pytest.mark.asyncio
async def test_save_empty_article():
    """Пустая статья не сохраняется."""
    empty_article = Article(url='https://test.com/empty')
    result = await save_article_to_cache(empty_article)
    assert result is False
