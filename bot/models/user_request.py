"""Модель данных запроса пользователя."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.utils.privacy import pseudonymize_user_id
from bot.utils.url_utils import extract_domain

__all__ = ['UserRequest']


@dataclass
class UserRequest:
    """Запрос пользователя к боту."""

    user_id: int
    original_url: str = ''
    normalized_url: str = ''
    received_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
    processed_at: datetime | None = None
    paywall_info: PaywallInfo | None = None
    article: Article | None = None
    success: bool = False
    error_message: str | None = None
    error_type: str | None = None

    @property
    def processing_time_ms(self) -> float | None:
        """Время обработки в миллисекундах."""
        if not self.processed_at:
            return None
        delta = self.processed_at - self.received_at
        return delta.total_seconds() * 1000

    @property
    def has_error(self) -> bool:
        """Была ли ошибка при обработке."""
        return self.error_message is not None

    def complete(
        self,
        article: Article | None = None,
        error: Exception | None = None,
    ) -> None:
        """Завершить запрос результатом или ошибкой."""
        self.processed_at = datetime.now(UTC)

        if article:
            self.article = article
            self.success = True
        elif error:
            self.success = False
            self.error_message = str(error)
            self.error_type = error.__class__.__name__

    def to_log_dict(self) -> dict[str, object]:
        """Вернуть безопасные операционные метаданные."""
        url = self.normalized_url or self.original_url
        base: dict[str, object] = {
            'user_hash': pseudonymize_user_id(self.user_id),
            'domain': extract_domain(url),
            'received_at': self.received_at.isoformat(),
            'processed_at': (
                self.processed_at.isoformat()
                if self.processed_at else None
            ),
            'processing_time_ms': self.processing_time_ms,
            'success': self.success,
            'error_type': self.error_type,
        }

        if self.paywall_info:
            info = self.paywall_info
            base['paywall'] = {
                'domain': info.domain,
                'type': str(info.paywall_type),
                'method': (
                    str(info.suggested_method)
                    if info.suggested_method
                    else None
                ),
                'platform': info.platform,
            }

        if self.article:
            base['article'] = {
                'content_length': len(self.article.content),
                'method': self.article.extraction_method,
            }

        return base

    def __str__(self) -> str:
        """Краткое privacy-safe представление."""
        status = 'success' if self.success else 'failure'
        url = self.normalized_url or self.original_url
        return (
            'UserRequest('
            f'user={pseudonymize_user_id(self.user_id)}, '
            f'domain={extract_domain(url)}, '
            f'status={status})'
        )
