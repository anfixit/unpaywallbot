"""Модель данных статьи.

Определяет структуру извлечённого контента, который будет
кешироваться и отправляться пользователю.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from bot.constants import MAX_MESSAGE_LENGTH

__all__ = ['Article']


@dataclass
class Article:
    """Извлечённая статья из-за paywall.

    Все поля опциональны, кроме url, так как не все сайты
    отдают полные метаданные. Текст (content) может быть пустым,
    если извлечение не удалось.
    """

    # --- Обязательные поля ---
    url: str
    """Оригинальный URL статьи (нормализованный)."""

    # --- Основной контент ---
    content: str = ''
    """Полный текст статьи (может быть пустым при ошибке)."""

    # --- Метаданные (могут отсутствовать) ---
    title: Optional[str] = None
    """Заголовок статьи."""

    author: Optional[str] = None
    """Автор или список авторов через запятую."""

    published_at: Optional[datetime] = None
    """Дата публикации (если удалось распарсить)."""

    # --- Служебные поля ---
    extracted_at: datetime = field(default_factory=datetime.now)
    """Время извлечения (UTC)."""

    paywall_type: Optional[str] = None
    """Тип paywall, с которым столкнулись (из constants.PaywallType)."""

    extraction_method: Optional[str] = None
    """Метод, которым удалось извлечь (из constants.BypassMethod)."""

    @property
    def content_preview(self) -> str:
        """Первые 200 символов текста для логов и превью."""
        if not self.content:
            return ''
        return self.content[:200].replace('\n', ' ').strip()

    @property
    def is_empty(self) -> bool:
        """Проверить, удалось ли извлечь контент."""
        return not self.content.strip()

    @property
    def telegram_safe_content(self) -> list[str]:
        """Разбить контент на части для Telegram (лимит 4096).

        Returns:
            Список строк, каждая ≤ MAX_MESSAGE_LENGTH.
            Пустой список, если контента нет.
        """
        if self.is_empty:
            return []

        # Простое разбиение по длине
        # TODO: в будущем заменить на text_formatter.py с умным разбиением
        result = []
        remaining = self.content

        while remaining:
            chunk = remaining[:MAX_MESSAGE_LENGTH]
            result.append(chunk)
            remaining = remaining[MAX_MESSAGE_LENGTH:]

        return result

    def __str__(self) -> str:
        """Краткое представление для логов."""
        return (
            f'Article('
            f'url={self.url}, '
            f'title={self.title or "None"}, '
            f'content_len={len(self.content)})'
        )
