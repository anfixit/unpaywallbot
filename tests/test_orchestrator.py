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
def orchestrator(
    mock_classifier,
    mock_account_manager,
    mock_extractor,
):
    """Оркестратор с моками."""
    return Orchestrator(
        classifier=mock_classifier,
        account_manager=mock_account_manager,
        extractor=mock_extractor,
    )


def _patch_cache():
    """Патч для кеша — get и save."""
    return (
        patch(
            'bot.services.orchestrator'
            '.get_cached_article',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            'bot.services.orchestrator'
            '.save_article_to_cache',
            new_callable=AsyncMock,
            return_value=True,
        ),
    )


def _patch_unknown_chain(
    js_result=None,
    googlebot_result=None,
    archive_result=None,
):
    """Патч для всей цепочки _handle_unknown.

    js_disable → googlebot_spoof → archive.
    """
    return (
        patch(
            'bot.services.orchestrator'
            '.fetch_via_js_disable',
            new_callable=AsyncMock,
            return_value=js_result,
        ),
        patch(
            'bot.services.orchestrator'
            '.fetch_via_googlebot_spoof',
            new_callable=AsyncMock,
            return_value=googlebot_result,
        ),
        patch(
            'bot.services.orchestrator'
            '.fetch_via_archive',
            new_callable=AsyncMock,
            return_value=archive_result,
        ),
    )


@pytest.mark.asyncio
async def test_process_url_cache_hit(
    orchestrator,
    mock_classifier,
) -> None:
    """Если статья в кеше — возвращаем её."""
    cached_article = Article(
        url='https://test.com',
        content='Cached content',
    )

    with patch(
        'bot.services.orchestrator'
        '.get_cached_article',
        new_callable=AsyncMock,
        return_value=cached_article,
    ):
        result = await orchestrator.process_url(
            'https://test.com',
        )

    assert result.success is True
    assert result.article == cached_article
    mock_classifier.classify.assert_not_called()


@pytest.mark.asyncio
async def test_process_url_unknown_paywall(
    orchestrator,
    mock_classifier,
) -> None:
    """Неизвестный paywall — цепочка до archive."""
    mock_classifier.classify.return_value = (
        PaywallInfo.unknown('https://test.com')
    )

    p_get, p_save = _patch_cache()
    p_js, p_google, p_archive = _patch_unknown_chain(
        js_result=None,
        googlebot_result=None,
        archive_result=Article(
            url='https://test.com',
            content='Archived content',
        ),
    )

    with (
        p_get, p_save,
        p_js, p_google, p_archive as mock_archive,
    ):
        result = await orchestrator.process_url(
            'https://test.com',
        )

    assert result.success is True
    mock_archive.assert_called_once()


@pytest.mark.asyncio
async def test_process_url_with_platform(
    orchestrator,
    mock_classifier,
) -> None:
    """Если есть платформа — делегируем ей."""
    paywall_info = PaywallInfo(
        url='https://spiegel.de/plus',
        domain='spiegel.de',
        paywall_type=PaywallType.FREEMIUM,
        platform='german_freemium',
    )
    mock_classifier.classify.return_value = (
        paywall_info
    )

    mock_platform = AsyncMock()
    mock_platform.handle.return_value = Article(
        url='https://spiegel.de/plus',
        content='Platform content',
    )
    orchestrator.platforms['german_freemium'] = (
        mock_platform
    )

    p_get, p_save = _patch_cache()

    with p_get, p_save:
        result = await orchestrator.process_url(
            'https://spiegel.de/plus',
            user_id=123,
        )

    assert result.success is True
    mock_platform.handle.assert_called_once()


@pytest.mark.asyncio
async def test_process_url_with_method(
    orchestrator,
    mock_classifier,
) -> None:
    """Если нет платформы, но есть метод."""
    paywall_info = PaywallInfo(
        url='https://nytimes.com/article',
        domain='nytimes.com',
        paywall_type=PaywallType.METERED,
        suggested_method=(
            BypassMethod.GOOGLEBOT_SPOOF
        ),
    )
    mock_classifier.classify.return_value = (
        paywall_info
    )

    p_get, p_save = _patch_cache()

    with (
        p_get,
        p_save,
        patch(
            'bot.services.orchestrator'
            '.fetch_via_googlebot_spoof',
            new_callable=AsyncMock,
            return_value=Article(
                url='https://nytimes.com/article',
                content='Article content',
            ),
        ) as mock_method,
    ):
        result = await orchestrator.process_url(
            'https://nytimes.com/article',
        )

    assert result.success is True
    mock_method.assert_called_once()


@pytest.mark.asyncio
async def test_process_url_fallback(
    orchestrator,
    mock_classifier,
) -> None:
    """Если основной метод не сработал — fallback."""
    paywall_info = PaywallInfo(
        url='https://failing-site.com',
        domain='failing-site.com',
        paywall_type=PaywallType.UNKNOWN,
    )
    mock_classifier.classify.return_value = (
        paywall_info
    )

    p_get, p_save = _patch_cache()
    p_js, p_google, p_archive = _patch_unknown_chain(
        js_result=None,
        googlebot_result=None,
        archive_result=Article(
            url='https://failing-site.com',
            content='Fallback content',
        ),
    )

    with (
        p_get, p_save,
        p_js, p_google, p_archive as mock_archive,
    ):
        result = await orchestrator.process_url(
            'https://failing-site.com',
        )

    assert result.success is True
    mock_archive.assert_called_once()
