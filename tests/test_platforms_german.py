"""Тесты для немецкой платформы."""

from unittest.mock import AsyncMock, patch

import pytest

from bot.constants import PaywallType
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.services.platforms.german_freemium import (
    GermanFreemiumPlatform,
)

# Контент длиннее _MIN_ARTICLE_LENGTH (500),
# чтобы _is_full_article() вернул True.
_FULL_CONTENT = 'A' * 600

_MODULE = 'bot.services.platforms.german_freemium'


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
        f'{_MODULE}.fetch_via_js_disable',
        new_callable=AsyncMock,
        return_value=Article(
            url='https://spiegel.de/kultur/artikel',
            content=_FULL_CONTENT,
        ),
    ) as mock_js:
        result = await platform.handle(
            'https://www.spiegel.de/kultur/artikel',
            paywall_info,
        )

    assert result is not None
    assert len(result.content) >= 500
    mock_js.assert_called_once()


@pytest.mark.asyncio
async def test_german_platform_premium_article(
    platform_with_auth,
    paywall_info,
) -> None:
    """Премиум: js_disable мало → googlebot."""
    short_article = Article(
        url='https://spiegel.de/plus/artikel',
        content='Лид',  # < 500 символов
    )
    full_article = Article(
        url='https://spiegel.de/plus/artikel',
        content=_FULL_CONTENT,
    )

    with (
        patch(
            f'{_MODULE}.fetch_via_js_disable',
            new_callable=AsyncMock,
            return_value=short_article,
        ),
        patch(
            f'{_MODULE}.fetch_via_googlebot_spoof',
            new_callable=AsyncMock,
            return_value=full_article,
        ) as mock_google,
    ):
        result = await platform_with_auth.handle(
            'https://www.spiegel.de/plus/artikel',
            paywall_info,
            user_id=123,
        )

    assert result is not None
    assert len(result.content) >= 500
    mock_google.assert_called_once()


@pytest.mark.asyncio
async def test_german_platform_fallback_archive(
    platform,
    paywall_info,
) -> None:
    """Если js_disable и googlebot не помогли."""
    with (
        patch(
            f'{_MODULE}.fetch_via_js_disable',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            f'{_MODULE}.fetch_via_googlebot_spoof',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            f'{_MODULE}.fetch_via_archive',
            new_callable=AsyncMock,
            return_value=Article(
                url='https://spiegel.de/artikel',
                content=_FULL_CONTENT,
            ),
        ) as mock_archive,
    ):
        result = await platform.handle(
            'https://www.spiegel.de/kultur/artikel',
            paywall_info,
        )

    assert result is not None
    mock_archive.assert_called_once()


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
