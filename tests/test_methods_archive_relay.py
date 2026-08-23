"""Тесты read-only archive relay."""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from bot.constants import BypassMethod
from bot.models.article import Article
from bot.services.methods import archive_relay
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


@pytest.mark.asyncio
async def test_archive_uses_proxy_when_configured(
    monkeypatch,
) -> None:
    """Запросы к архиву идут через настроенный прокси."""
    captured: dict[str, object] = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(
            side_effect=httpx.ConnectError('stop'),
        )
        client.aclose = AsyncMock()
        return client

    monkeypatch.setattr(
        archive_relay.settings,
        'archive_proxy_url',
        'http://archive-proxy:1080',
    )
    monkeypatch.setattr(
        archive_relay,
        'create_safe_http_client',
        fake_client,
    )

    result = await archive_relay.fetch_via_archive(
        'https://example.com/article',
        extractor=Mock(),
    )

    assert result is None
    assert captured['proxy'] == 'http://archive-proxy:1080'
    # Недоступный архив не должен съедать бюджет запроса.
    assert captured['connect_timeout_seconds'] <= 10


@pytest.mark.asyncio
async def test_archive_without_proxy_connects_directly(
    monkeypatch,
) -> None:
    """Без настройки прокси не используется."""
    captured: dict[str, object] = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(
            side_effect=httpx.ConnectError('stop'),
        )
        client.aclose = AsyncMock()
        return client

    monkeypatch.setattr(
        archive_relay.settings, 'archive_proxy_url', '',
    )
    monkeypatch.setattr(
        archive_relay, 'create_safe_http_client', fake_client,
    )

    await archive_relay.fetch_via_archive(
        'https://example.com/article',
        extractor=Mock(),
    )

    assert captured['proxy'] is None
