"""Извлечение основного контента из HTML-страниц.

Использует readability-lxml для парсинга статьи,
выделения заголовка, автора и текста.
"""

import re

import lxml.html
import readability
from lxml.etree import ParserError

from bot.models.article import Article
from bot.utils.url_utils import normalize_url

__all__ = ['ContentExtractor']

_AUTHOR_PATTERNS: list[str] = [
    r'<meta[^>]+name="author"'
    r'[^>]+content="([^"]+)"',
    r'<meta[^>]+property="article:author"'
    r'[^>]+content="([^"]+)"',
    r'class="[^"]*author[^"]*"[^>]*>([^<]+)',
    r'class="[^"]*byline[^"]*"[^>]*>([^<]+)',
]

_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


class ContentExtractor:
    """Извлекает читаемый контент из HTML."""

    def __init__(
        self,
        min_text_length: int = 200,
    ) -> None:
        """Инициализировать экстрактор.

        Args:
            min_text_length: Минимальная длина текста
                для успешного извлечения.
        """
        self.min_text_length = min_text_length

    def extract(
        self,
        html: str,
        url: str,
    ) -> Article | None:
        """Извлечь статью из HTML.

        Args:
            html: HTML-код страницы.
            url: Исходный URL (для нормализации).

        Returns:
            Article или None.
        """
        if not html or not html.strip():
            return None

        try:
            doc = readability.Document(html)
            content_html = doc.summary()
            title = doc.title()

            text = self._html_to_text(content_html)

            if len(text) < self.min_text_length:
                return None

            author = self._extract_author(html)

            return Article(
                url=normalize_url(url),
                content=text,
                title=title or None,
                author=author,
            )

        except (ParserError, ValueError, TypeError):
            return None

    def _html_to_text(self, html: str) -> str:
        """Конвертировать HTML в чистый текст.

        Args:
            html: HTML-код.

        Returns:
            Чистый текст с нормализованными пробелами.
        """
        try:
            root = lxml.html.fromstring(html)
            text = root.text_content()
        except (ParserError, ValueError):
            text = self._strip_tags(html)

        lines = (
            line.strip()
            for line in text.splitlines()
        )
        chunks = (
            chunk.strip()
            for line in lines
            for chunk in line.split('  ')
        )
        text = ' '.join(
            chunk for chunk in chunks if chunk
        )

        return text.strip()

    @staticmethod
    def _strip_tags(html: str) -> str:
        """Удалить HTML-теги (запасной метод)."""
        text = _TAG_RE.sub(' ', html)
        text = _WHITESPACE_RE.sub(' ', text)
        return text.strip()

    @staticmethod
    def _extract_author(html: str) -> str | None:
        """Извлечь автора из HTML.

        Args:
            html: HTML-код страницы.

        Returns:
            Имя автора или None.
        """
        for pattern in _AUTHOR_PATTERNS:
            match = re.search(
                pattern, html, re.IGNORECASE,
            )
            if match:
                return match.group(1).strip()

        return None
