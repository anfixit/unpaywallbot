"""Тесты для метода headless_auth."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.models.article import Article
from bot.services.methods.headless_auth import fetch_via_headless_auth


@pytest.fixture
def mock_account_manager():
    """Мок менеджера аккаунтов."""
    manager = AsyncMock()
    manager.get_account_for_url = AsyncMock(return_value=Mock(
        email='test@example.com',
        password='password',
        session_cookies=None,
    ))
    manager.save_account = AsyncMock()
    return manager


@pytest.mark.asyncio
@patch('bot.services.methods.headless_auth.async_playwright')
async def test_headless_auth_success(mock_playwright, mock_account_manager):
    """Успешное извлечение через headless."""
    # Мок браузера
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    # Настройка цепочки вызовов
    mock_playwright.return_value.start = AsyncMock(return_value=Mock(
        chromium=Mock(launch=AsyncMock(return_value=mock_browser))
    ))
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)

    # Мок ответа
    mock_response = Mock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_response)
    mock_page.content = AsyncMock(return_value='<html><body>Content</body></html>')

    # Мок экстрактора
    mock_extractor = Mock()
    mock_extractor.extract = Mock(
        return_value=Article(url='https://test.com', content='Content')
    )

    result = await fetch_via_headless_auth(
        'https://test.com',
        user_id=123,
        account_manager=mock_account_manager,
        extractor=mock_extractor,
    )

    assert result is not None
    assert result.content == 'Content'
    mock_account_manager.get_account_for_url.assert_called_once()
    mock_account_manager.save_account.assert_called_once()
