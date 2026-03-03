"""Тесты для метода headless_auth."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.models.article import Article
from bot.services.methods.headless_auth import (
    fetch_via_headless_auth,
)


@pytest.fixture
def mock_account_manager():
    """Мок менеджера аккаунтов."""
    manager = AsyncMock()
    manager.get_account_for_url = AsyncMock(
        return_value=Mock(
            email='test@example.com',
            password='password',
            session_cookies=None,
        ),
    )
    manager.save_account = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_headless_auth_success(
    mock_account_manager,
) -> None:
    """Успешное извлечение через headless."""
    # Мок страницы
    mock_page = AsyncMock()
    mock_response = Mock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(
        return_value=mock_response,
    )
    mock_page.content = AsyncMock(
        return_value=(
            '<html><body>Content</body></html>'
        ),
    )
    mock_page.close = AsyncMock()

    # Мок контекста
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(
        return_value=mock_page,
    )
    mock_context.close = AsyncMock()

    # Мок браузера
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(
        return_value=mock_context,
    )
    mock_browser.close = AsyncMock()

    # Мок playwright — async context manager
    mock_pw = AsyncMock()
    mock_pw.chromium = Mock()
    mock_pw.chromium.launch = AsyncMock(
        return_value=mock_browser,
    )

    mock_pw_cm = AsyncMock()
    mock_pw_cm.__aenter__ = AsyncMock(
        return_value=mock_pw,
    )
    mock_pw_cm.__aexit__ = AsyncMock(
        return_value=False,
    )

    # Мок экстрактора
    mock_extractor = Mock()
    mock_extractor.extract = Mock(
        return_value=Article(
            url='https://test.com',
            content='Content',
        ),
    )

    with patch(
        'bot.services.methods.headless_auth'
        '.async_playwright',
        return_value=mock_pw_cm,
    ):
        result = await fetch_via_headless_auth(
            'https://test.com',
            user_id=123,
            account_manager=mock_account_manager,
            extractor=mock_extractor,
        )

    assert result is not None
    assert result.content == 'Content'
