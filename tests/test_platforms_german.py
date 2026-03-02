"""Тесты для немецкой платформы."""

from unittest.mock import Mock, patch

import pytest

from bot.constants import PaywallType
from bot.models.paywall_info import PaywallInfo
from bot.services.platforms.german_freemium import GermanFreemiumPlatform


@pytest.fixture
def platform():
    """Платформа для тестов."""
    return GermanFreemiumPlatform()


@pytest.fixture
def paywall_info():
    """Базовая информация о paywall."""
    return PaywallInfo(
        url='https://www.spiegel.de/artikel',
        domain='spiegel.de',
        paywall_type=PaywallType.FREEMIUM,
    )


@pytest.mark.asyncio
async def test_german_platform_open_article(platform, paywall_info):
    """Открытая статья (без премиум-маркеров) идёт через js_disable."""
    with patch('bot.services.platforms.german_freemium.fetch_via_js_disable') as mock_js:
        mock_js.return_value = Mock(spec=Article)

        result = await platform.handle(
            'https://www.spiegel.de/kultur/artikel',
            paywall_info,
        )

        assert result is not None
        mock_js.assert_called_once()


@pytest.mark.asyncio
async def test_german_platform_premium_article(platform, paywall_info):
    """Премиум-статья пробует headless."""
    with patch('bot.services.platforms.german_freemium.fetch_via_headless_auth') as mock_headless:
        mock_headless.return_value = Mock(spec=Article)

        result = await platform.handle(
            'https://www.spiegel.de/plus/artikel',
            paywall_info,
            user_id=123,
        )

        assert result is not None
        mock_headless.assert_called_once()


def test_check_if_premium(platform):
    """Проверка определения премиум-контента."""
    assert platform._check_if_premium(
        'https://www.spiegel.de/plus/artikel',
        'spiegel.de',
    ) is True

    assert platform._check_if_premium(
        'https://www.spiegel.de/kultur/artikel',
        'spiegel.de',
    ) is False
