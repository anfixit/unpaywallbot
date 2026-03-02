"""Модель данных статьи.

Определяет структуру извлечённого контента, который
будет кешироваться и отправляться пользователю.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

__all__ = ['Article']


@dataclass
class Article:
    """Извлечённая статья из-за paywall.

    Все поля кроме url опциональны, так как не все
    сайты отдают полные метаданные. Текст (content)
    может быть пустым, если извлечение не удалось.
    """

    # --- Обязательные поля ---
    url: str
    """Оригинальный URL статьи (нормализованный)."""

    # --- Основной контент ---
    content: str = ''
    """Полный текст статьи."""

    # --- Метаданные (могут отсутствовать) ---
    title: str | None = None
    """Заголовок статьи."""

    author: str | None = None
    """Автор или список авторов через запятую."""

    published_at: datetime | None = None
    """Дата публикации (если удалось распарсить)."""

    # --- Служебные поля ---
    extracted_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
    """Время извлечения (UTC)."""

    paywall_type: str | None = None
    """Тип paywall (из constants.PaywallType)."""

    extraction_method: str | None = None
    """Метод извлечения (из constants.BypassMethod)."""

    @property
    def content_preview(self) -> str:
        """Первые 200 символов для логов и превью."""
        if not self.content:
            return ''
        return (
            self.content[:200]
            .replace('\n', ' ')
            .strip()
        )

    @property
    def is_empty(self) -> bool:
        """Проверить, удалось ли извлечь контент."""
        return not self.content.strip()

    def __str__(self) -> str:
        """Краткое представление для логов."""
        return (
            f'Article('
            f'url={self.url}, '
            f'title={self.title or "None"}, '
            f'content_len={len(self.content)})'
        )
