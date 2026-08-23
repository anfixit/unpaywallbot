"""Тесты для метода googlebot_spoof."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from bot.constants import MAX_RETRY_COUNT
from bot.models.article import Article
from bot.services.methods.googlebot_spoof import fetch_via_googlebot_spoof


@pytest.mark.asyncio
async def test_googlebot_spoof_success() -> None:
    """Успешное извлечение через googlebot_spoof."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'text/html'}
    mock_response.text = '<html><body>Test content</body></html>'

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_extractor = Mock()
    mock_extractor.extract = Mock(
        return_value=Article(
            url='https://test.com',
            content='Test content',
        )
    )

    result = await fetch_via_googlebot_spoof(
        'https://test.com',
        extractor=mock_extractor,
        client=mock_client,
    )

    assert result is not None
    assert result.content == 'Test content'


@pytest.mark.asyncio
async def test_googlebot_spoof_retry_on_403() -> None:
    """При 403 пробуем ещё раз с другими заголовками."""
    mock_response_403 = Mock()
    mock_response_403.status_code = 403

    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.headers = {'content-type': 'text/html'}
    mock_response_200.text = '<html><body>Content</body></html>'

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(
        side_effect=[
            mock_response_403,
            mock_response_200,
        ],
    )

    mock_extractor = Mock()
    mock_extractor.extract = Mock(
        return_value=Article(
            url='https://test.com',
            content='Content',
        ),
    )

    with patch(
        'bot.services.methods.googlebot_spoof'
        '.asyncio.sleep',
        new=AsyncMock(),
    ) as sleep:
        result = await fetch_via_googlebot_spoof(
            'https://test.com',
            extractor=mock_extractor,
            client=mock_client,
        )

    assert result is not None
    assert mock_client.get.call_count == 2
    # Повтор после 403 выполняется с паузой.
    sleep.assert_awaited_once()
    assert sleep.await_args.args[0] > 0


@pytest.mark.asyncio
async def test_googlebot_spoof_stops_after_last_attempt() -> None:
    """После последней попытки пауза не нужна."""
    blocked = Mock()
    blocked.status_code = 429

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=blocked)

    with patch(
        'bot.services.methods.googlebot_spoof'
        '.asyncio.sleep',
        new=AsyncMock(),
    ) as sleep:
        result = await fetch_via_googlebot_spoof(
            'https://test.com',
            extractor=Mock(),
            client=mock_client,
        )

    assert result is None
    assert mock_client.get.call_count == MAX_RETRY_COUNT
    assert sleep.await_count == MAX_RETRY_COUNT - 1
