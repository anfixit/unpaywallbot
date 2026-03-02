"""Тесты для метода js_disable."""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from bot.models.article import Article
from bot.services.methods.js_disable import fetch_via_js_disable


@pytest.mark.asyncio
async def test_fetch_via_js_disable_success() -> None:
    """Успешное извлечение через js_disable."""
    # Mock HTTP-клиента
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'text/html'}
    mock_response.text = '<html><body>Test content</body></html>'

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    # Mock экстрактора
    mock_extractor = Mock()
    mock_extractor.extract = Mock(
        return_value=Article(
            url='https://test.com',
            content='Test content',
        )
    )

    result = await fetch_via_js_disable(
        'https://test.com',
        extractor=mock_extractor,
        client=mock_client,
    )

    assert result is not None
    assert result.content == 'Test content'
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_via_js_disable_not_html() -> None:
    """Если ответ не HTML — возвращаем None."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'image/jpeg'}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await fetch_via_js_disable(
        'https://test.com',
        client=mock_client,
    )

    assert result is None


@pytest.mark.asyncio
async def test_fetch_via_js_disable_http_error() -> None:
    """При HTTP-ошибке пробрасываем исключение."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
        '404 Not Found',
        request=Mock(),
        response=Mock(status_code=404),
    ))

    with pytest.raises(httpx.HTTPStatusError):
        await fetch_via_js_disable(
            'https://test.com',
            client=mock_client,
        )
