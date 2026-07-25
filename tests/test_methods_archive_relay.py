"""Тесты read-only archive relay."""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from bot.constants import BypassMethod
from bot.models.article import Article
from bot.services.methods.archive_relay import fetch_via_archive


@pytest.mark.asyncio
async def test_archive_reads_existing_snapshot_only() -> None:
    """Метод не создаёт новый snapshot через POST."""
    request = httpx.Request(
        'GET',
        'https://archive.ph/newest/https://example.com/article',
    )
    response = httpx.Response(
        200,
        text='<html>archived article</html>',
        request=request,
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock()
    extractor = Mock()
    article = Article(
        url='https://example.com/article',
        content='Archived text',
    )
    extractor.extract.return_value = article

    result = await fetch_via_archive(
        article.url,
        extractor=extractor,
        client=client,
    )

    assert result is article
    assert result.extraction_method == BypassMethod.ARCHIVE_RELAY
    client.get.assert_awaited_once()
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_archive_wait_page_returns_none() -> None:
    """Страница ожидания не запускает создание snapshot."""
    request = httpx.Request(
        'GET',
        'https://archive.ph/newest/https://example.com/article',
    )
    response = httpx.Response(
        200,
        text='Saving page',
        request=request,
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock()
    extractor = Mock()

    result = await fetch_via_archive(
        'https://example.com/article',
        extractor=extractor,
        client=client,
    )

    assert result is None
    extractor.extract.assert_not_called()
    client.post.assert_not_called()
