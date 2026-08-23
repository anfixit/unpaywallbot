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


@pytest.fixture(autouse=True)
def _clear_cooldown():
    """Каждый тест начинает без активной паузы."""
    archive_relay.reset_cooldown()
    yield
    archive_relay.reset_cooldown()


def _client_returning(status_code: int, text: str):
    """Клиент, отдающий заданный ответ."""
    response = Mock()
    response.status_code = status_code
    response.text = text
    response.headers = {'content-type': 'text/html'}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)
    client.aclose = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_rate_limit_starts_cooldown() -> None:
    """429 с капчей включает паузу вместо повторов."""
    client = _client_returning(429, '<title>archive.ph</title> CAPTCHA')

    result = await archive_relay.fetch_via_archive(
        'https://example.com/a',
        extractor=Mock(),
        client=client,
    )

    assert result is None
    assert client.get.await_count == 1
    assert archive_relay._cooldown_remaining() > 0


@pytest.mark.asyncio
async def test_cooldown_skips_further_requests() -> None:
    """Во время паузы запрос к архиву не уходит вовсе."""
    blocked = _client_returning(429, 'CAPTCHA')
    await archive_relay.fetch_via_archive(
        'https://example.com/a',
        extractor=Mock(),
        client=blocked,
    )

    second = _client_returning(200, '<html>snapshot</html>')
    result = await archive_relay.fetch_via_archive(
        'https://example.com/b',
        extractor=Mock(),
        client=second,
    )

    assert result is None
    second.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_captcha_page_with_200_also_counts() -> None:
    """Заслон распознаётся и без кода 429."""
    client = _client_returning(
        200, '<html><title>Are you a robot?</title></html>',
    )

    result = await archive_relay.fetch_via_archive(
        'https://example.com/a',
        extractor=Mock(),
        client=client,
    )

    assert result is None
    assert archive_relay._cooldown_remaining() > 0
