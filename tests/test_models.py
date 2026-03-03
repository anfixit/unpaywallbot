"""Тесты для моделей данных."""

from bot.constants import PaywallType
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.models.user_request import UserRequest


def test_article_empty() -> None:
    """Проверка пустой статьи."""
    article = Article(url='https://test.com')
    assert article.is_empty is True
    assert article.content_preview == ''


def test_article_with_content() -> None:
    """Проверка статьи с контентом."""
    content = 'A' * 5000
    article = Article(
        url='https://test.com',
        content=content,
        title='Test Title',
    )
    assert article.is_empty is False
    assert article.title == 'Test Title'
    assert len(article.content) == 5000


def test_paywall_info_unknown() -> None:
    """Создание unknown paywall."""
    info = PaywallInfo.unknown(
        'https://test.com/article',
    )
    assert info.domain == 'test.com'
    assert info.paywall_type == PaywallType.UNKNOWN
    assert info.suggested_method is None
    assert info.is_known is False
    assert info.can_bypass is False


def test_user_request_complete_success() -> None:
    """Успешное завершение запроса."""
    request = UserRequest(
        user_id=123,
        username='testuser',
        original_url='https://test.com',
    )

    article = Article(
        url='https://test.com',
        content='Test content',
        title='Test',
    )

    request.complete(article=article)

    assert request.success is True
    assert request.processed_at is not None
    assert request.processing_time_ms is not None
    assert request.article == article


def test_user_request_complete_error() -> None:
    """Завершение запроса с ошибкой."""
    request = UserRequest(
        user_id=123,
        original_url='https://test.com',
    )

    error = ValueError('Test error')
    request.complete(error=error)

    assert request.success is False
    assert request.error_message == 'Test error'
    assert request.error_type == 'ValueError'
