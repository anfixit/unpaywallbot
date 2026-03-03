"""Тесты для немецкой платформы."""

from unittest.mock import AsyncMock, patch

import pytest

from bot.constants import PaywallType
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.services.platforms.german_freemium import (
    GermanFreemiumPlatform,
)


@pytest.fixture
def platform():
    """Платформа для тестов."""
    return GermanFreemiumPlatform()


@pytest.fixture
def platform_with_auth():
    """Платформа с менеджером аккаунтов."""
    return GermanFreemiumPlatform(
        account_manager=AsyncMock(),
    )


@pytest.fixture
def paywall_info():
    """Базовая информация о paywall."""
    return PaywallInfo(
        url='https://www.spiegel.de/artikel',
        domain='spiegel.de',
        paywall_type=PaywallType.FREEMIUM,
    )


@pytest.mark.asyncio
async def test_german_platform_open_article(
    platform,
    paywall_info,
) -> None:
    """Открытая статья через js_disable."""
    with patch(
        'bot.services.platforms.german_freemium'
        '.fetch_via_js_disable',
        new_callable=AsyncMock,
        return_value=Article(
            url='https://spiegel.de/kultur/artikel',
            content='Open content',
        ),
    ) as mock_js:
        result = await platform.handle(
            'https://www.spiegel.de/kultur/artikel',
            paywall_info,
        )

    assert result is not None
    mock_js.assert_called_once()


@pytest.mark.asyncio
async def test_german_platform_premium_article(
    platform_with_auth,
    paywall_info,
) -> None:
    """Премиум-статья пробует headless."""
    with patch(
        'bot.services.platforms.german_freemium'
        '.fetch_via_headless_auth',
        new_callable=AsyncMock,
        return_value=Article(
            url='https://spiegel.de/plus/artikel',
            content='Premium content',
        ),
    ) as mock_headless:
        result = await platform_with_auth.handle(
            'https://www.spiegel.de/plus/artikel',
            paywall_info,
            user_id=123,
        )

    assert result is not None
    mock_headless.assert_called_once()


def test_check_if_premium(platform) -> None:
    """Проверка определения премиум-контента."""
    assert platform._check_if_premium(
        'https://www.spiegel.de/plus/artikel',
        'spiegel.de',
    ) is True

    assert platform._check_if_premium(
        'https://www.spiegel.de/kultur/artikel',
        'spiegel.de',
    ) is False
