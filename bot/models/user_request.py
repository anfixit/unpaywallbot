"""Модель данных запроса пользователя.

Используется для аудита, статистики и обнаружения аномалий
(раздел middleware/access_log.py).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo

__all__ = ['UserRequest']


@dataclass
class UserRequest:
    """Запрос пользователя к боту.

    Создаётся при получении URL от пользователя и заполняется
    по мере обработки. Используется для логирования и анализа.
    """

    # --- Данные пользователя ---
    user_id: int
    """Telegram user ID."""

    username: Optional[str] = None
    """Telegram username (если есть)."""

    # --- Данные запроса ---
    original_url: str
    """URL, который отправил пользователь (сырой)."""

    normalized_url: str = ''
    """Нормализованный URL (после clean_url, normalize_url)."""

    # --- Временные метки ---
    received_at: datetime = field(default_factory=datetime.now)
    """Время получения запроса (UTC)."""

    processed_at: Optional[datetime] = None
    """Время завершения обработки."""

    # --- Результаты обработки ---
    paywall_info: Optional[PaywallInfo] = None
    """Результат классификации paywall."""

    article: Optional[Article] = None
    """Извлечённая статья (если успешно)."""

    # --- Статус и ошибки ---
    success: bool = False
    """Успешно ли извлечена статья."""

    error_message: Optional[str] = None
    """Сообщение об ошибке (если была)."""

    error_type: Optional[str] = None
    """Тип ошибки (например, 'Timeout', 'AuthRequired')."""

    @property
    def processing_time_ms(self) -> Optional[float]:
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
        article: Optional[Article] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Завершить запрос (установить результат и время).

        Args:
            article: Успешно извлечённая статья (если есть).
            error: Исключение, если произошло.
        """
        self.processed_at = datetime.now()

        if article:
            self.article = article
            self.success = True
        elif error:
            self.success = False
            self.error_message = str(error)
            self.error_type = error.__class__.__name__

    def to_log_dict(self) -> dict:
        """Подготовить словарь для JSON-логирования.

        Используется в access_log.py для структурированных логов.
        """
        base = {
            'user_id': self.user_id,
            'username': self.username,
            'url': self.normalized_url or self.original_url,
            'received_at': self.received_at.isoformat(),
            'processed_at': (
                self.processed_at.isoformat()
                if self.processed_at else None
            ),
            'processing_time_ms': self.processing_time_ms,
            'success': self.success,
            'error': self.error_message,
        }

        # Добавляем информацию о paywall (если есть)
        if self.paywall_info:
            base['paywall'] = {
                'domain': self.paywall_info.domain,
                'type': str(self.paywall_info.paywall_type),
                'method': (
                    str(self.paywall_info.suggested_method)
                    if self.paywall_info.suggested_method
                    else None
                ),
                'platform': self.paywall_info.platform,
            }

        # Добавляем метаданные статьи (если есть)
        if self.article and self.article.title:
            base['article'] = {
                'title': self.article.title,
                'author': self.article.author,
                'content_length': len(self.article.content),
            }

        return base

    def __str__(self) -> str:
        """Краткое представление для логов."""
        status = '✓' if self.success else '✗'
        return (
            f'UserRequest('
            f'user={self.user_id}, '
            f'url={self.original_url}, '
            f'status={status})'
        )
