"""Модель данных извлечённой статьи."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from bot.utils.url_utils import extract_domain

__all__ = ['Article']


@dataclass
class Article:
    """Извлечённая статья и служебные метаданные."""

    url: str
    content: str = ''
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    extracted_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
    paywall_type: str | None = None
    extraction_method: str | None = None

    @property
    def content_preview(self) -> str:
        """Вернуть первые 200 символов для интерфейса."""
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
        """Краткое privacy-safe представление."""
        return (
            'Article('
            f'domain={extract_domain(self.url)}, '
            f'content_len={len(self.content)}, '
            f'method={self.extraction_method})'
        )
