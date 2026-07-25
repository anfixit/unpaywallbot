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
    """Патч чтения и записи кеша."""
    return (
        patch(
            'bot.services.orchestrator.get_cached_article',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            'bot.services.orchestrator.save_article_to_cache',
            new_callable=AsyncMock,
            return_value=True,
        ),
    )


def _patch_unknown_chain(
    js_result=None,
    googlebot_result=None,
    archive_result=None,
):
    """Патч цепочки публичных методов."""
    return (
        patch(
            'bot.services.orchestrator.fetch_via_js_disable',
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
            'bot.services.orchestrator.fetch_via_archive',
            new_callable=AsyncMock,
            return_value=archive_result,
        ),
    )


@pytest.mark.asyncio
async def test_process_url_cache_hit(
    orchestrator,
    mock_classifier,
) -> None:
    """Кешированный ответ не записывается повторно."""
    cached_article = Article(
        url='https://test.com',
        content='Cached content',
        extraction_method=BypassMethod.JS_DISABLE,
    )

    with (
        patch(
            'bot.services.orchestrator.get_cached_article',
            new=AsyncMock(return_value=cached_article),
        ),
        patch(
            'bot.services.orchestrator.save_article_to_cache',
            new=AsyncMock(),
        ) as save_cache,
    ):
        result = await orchestrator.process_url(
            'https://test.com',
        )

    assert result.success is True
    assert result.article == cached_article
    mock_classifier.classify.assert_not_called()
    save_cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_url_unknown_uses_actual_archive_method(
    orchestrator,
    mock_classifier,
) -> None:
    """Архивный fallback не помечается как js_disable."""
    mock_classifier.classify.return_value = (
        PaywallInfo.unknown('https://test.com')
    )
    archived = Article(
        url='https://test.com',
        content='Archived content',
        extraction_method=BypassMethod.ARCHIVE_RELAY,
    )
    patch_get, patch_save = _patch_cache()
    patch_js, patch_google, patch_archive = (
        _patch_unknown_chain(
            js_result=None,
            googlebot_result=None,
            archive_result=archived,
        )
    )

    with (
        patch_get,
        patch_save as save_cache,
        patch_js,
        patch_google,
        patch_archive as archive_fetch,
    ):
        result = await orchestrator.process_url(
            'https://test.com',
        )

    assert result.success is True
    assert result.article is archived
    assert result.article.extraction_method == (
        BypassMethod.ARCHIVE_RELAY
    )
    archive_fetch.assert_awaited_once()
    save_cache.assert_awaited_once_with(archived)


@pytest.mark.asyncio
async def test_process_url_with_platform(
    orchestrator,
    mock_classifier,
) -> None:
    """Платформенный результат сохраняется до возврата."""
    paywall_info = PaywallInfo(
        url='https://spiegel.de/plus',
        domain='spiegel.de',
        paywall_type=PaywallType.FREEMIUM,
        platform='german_freemium',
    )
    mock_classifier.classify.return_value = paywall_info
    platform_article = Article(
        url='https://spiegel.de/plus',
        content='Platform content',
        extraction_method=BypassMethod.JS_DISABLE,
    )
    mock_platform = AsyncMock()
    mock_platform.handle.return_value = platform_article
    orchestrator.platforms['german_freemium'] = mock_platform
    patch_get, patch_save = _patch_cache()

    with patch_get, patch_save as save_cache:
        result = await orchestrator.process_url(
            'https://spiegel.de/plus',
            user_id=123,
        )

    assert result.success is True
    mock_platform.handle.assert_awaited_once()
    save_cache.assert_awaited_once_with(platform_article)


@pytest.mark.asyncio
async def test_process_url_with_method(
    orchestrator,
    mock_classifier,
) -> None:
    """Выбранный метод сохраняется как фактический."""
    paywall_info = PaywallInfo(
        url='https://nytimes.com/article',
        domain='nytimes.com',
        paywall_type=PaywallType.METERED,
        suggested_method=BypassMethod.GOOGLEBOT_SPOOF,
    )
    mock_classifier.classify.return_value = paywall_info
    article = Article(
        url='https://nytimes.com/article',
        content='Article content',
        extraction_method=BypassMethod.GOOGLEBOT_SPOOF,
    )
    patch_get, patch_save = _patch_cache()

    with (
        patch_get,
        patch_save,
        patch(
            'bot.services.orchestrator'
            '.fetch_via_googlebot_spoof',
            new=AsyncMock(return_value=article),
        ) as method_fetch,
    ):
        result = await orchestrator.process_url(
            'https://nytimes.com/article',
        )

    assert result.success is True
    assert result.article is article
    assert result.article.extraction_method == (
        BypassMethod.GOOGLEBOT_SPOOF
    )
    method_fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_primary_failure_preserves_archive_fallback_method(
    orchestrator,
    mock_classifier,
) -> None:
    """Fallback method replaces the proposed primary method."""
    paywall_info = PaywallInfo(
        url='https://failing-site.com/article',
        domain='failing-site.com',
        paywall_type=PaywallType.METERED,
        suggested_method=BypassMethod.GOOGLEBOT_SPOOF,
    )
    mock_classifier.classify.return_value = paywall_info
    archived = Article(
        url=paywall_info.url,
        content='Fallback content',
        extraction_method=BypassMethod.ARCHIVE_RELAY,
    )
    patch_get, patch_save = _patch_cache()

    with (
        patch_get,
        patch_save,
        patch(
            'bot.services.orchestrator'
            '.fetch_via_googlebot_spoof',
            new=AsyncMock(return_value=None),
        ),
        patch(
            'bot.services.orchestrator.fetch_via_archive',
            new=AsyncMock(return_value=archived),
        ),
    ):
        result = await orchestrator.process_url(
            paywall_info.url,
        )

    assert result.success is True
    assert result.article is archived
    assert result.article.extraction_method == (
        BypassMethod.ARCHIVE_RELAY
    )
