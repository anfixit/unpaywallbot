"""Тесты для оркестратора."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.constants import BypassMethod, PaywallType
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.services.orchestrator import Orchestrator


@pytest.fixture
def mock_classifier():
    """Мок классификатора."""
    classifier = AsyncMock()
    classifier.classify = AsyncMock()
    return classifier


@pytest.fixture
def mock_account_manager():
    """Мок менеджера аккаунтов."""
    return AsyncMock()


@pytest.fixture
def mock_extractor():
    """Мок экстрактора."""
    return Mock()


@pytest.fixture
def orchestrator(mock_classifier, mock_account_manager, mock_extractor):
    """Оркестратор с моками."""
    return Orchestrator(
        classifier=mock_classifier,
        account_manager=mock_account_manager,
        extractor=mock_extractor,
    )


@pytest.mark.asyncio
async def test_process_url_cache_hit(orchestrator, mock_classifier):
    """Если статья в кеше — возвращаем её."""
    cached_article = Article(
        url='https://test.com',
        content='Cached content',
    )

    with patch('bot.services.orchestrator.get_cached_article') as mock_get_cache:
        mock_get_cache.return_value = cached_article

        result = await orchestrator.process_url('https://test.com')

        assert result.success is True
        assert result.article == cached_article
        mock_classifier.classify.assert_not_called()


@pytest.mark.asyncio
async def test_process_url_unknown_paywall(orchestrator, mock_classifier):
    """Неизвестный тип paywall — используем archive.ph."""
    mock_classifier.classify.return_value = PaywallInfo.unknown('https://test.com')

    with patch('bot.services.orchestrator.fetch_via_archive') as mock_archive:
        mock_archive.return_value = Article(
            url='https://test.com',
            content='Archived content',
        )

        result = await orchestrator.process_url('https://test.com')

        assert result.success is True
        mock_archive.assert_called_once()
        assert result.paywall_info.paywall_type == PaywallType.UNKNOWN


@pytest.mark.asyncio
async def test_process_url_with_platform(orchestrator, mock_classifier):
    """Если есть платформа — делегируем ей."""
    paywall_info = PaywallInfo(
        url='https://spiegel.de/plus',
        domain='spiegel.de',
        paywall_type=PaywallType.FREEMIUM,
        platform='german_freemium',
    )
    mock_classifier.classify.return_value = paywall_info

    # Мок платформы
    mock_platform = AsyncMock()
    mock_platform.handle.return_value = Article(
        url='https://spiegel.de/plus',
        content='Platform content',
    )
    orchestrator.platforms['german_freemium'] = mock_platform

    result = await orchestrator.process_url('https://spiegel.de/plus', user_id=123)

    assert result.success is True
    mock_platform.handle.assert_called_once_with(
        'https://spiegel.de/plus',
        paywall_info,
        user_id=123,
    )


@pytest.mark.asyncio
async def test_process_url_with_method(orchestrator, mock_classifier):
    """Если нет платформы, но есть метод — используем его."""
    paywall_info = PaywallInfo(
        url='https://nytimes.com/article',
        domain='nytimes.com',
        paywall_type=PaywallType.METERED,
        suggested_method=BypassMethod.GOOGLEBOT_SPOOF,
    )
    mock_classifier.classify.return_value = paywall_info

    with patch('bot.services.orchestrator.fetch_via_googlebot_spoof') as mock_method:
        mock_method.return_value = Article(
            url='https://nytimes.com/article',
            content='Article content',
        )

        result = await orchestrator.process_url('https://nytimes.com/article')

        assert result.success is True
        mock_method.assert_called_once()


@pytest.mark.asyncio
async def test_process_url_fallback(orchestrator, mock_classifier):
    """Если всё провалилось — fallback на archive.ph."""
    paywall_info = PaywallInfo(
        url='https://failing-site.com',
        domain='failing-site.com',
        paywall_type=PaywallType.UNKNOWN,
    )
    mock_classifier.classify.return_value = paywall_info

    with patch('bot.services.orchestrator.fetch_via_archive') as mock_archive:
        mock_archive.return_value = Article(
            url='https://failing-site.com',
            content='Fallback content',
        )

        result = await orchestrator.process_url('https://failing-site.com')

        assert result.success is True
        mock_archive.assert_called_once()
