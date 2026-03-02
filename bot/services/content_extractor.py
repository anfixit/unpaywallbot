"""Извлечение основного контента из HTML-страниц.

Использует readability-lxml для парсинга статьи,
выделения заголовка, автора и текста.
"""


import lxml.html
import readability
from lxml.etree import ParserError

from bot.models.article import Article
from bot.utils.url_utils import normalize_url

__all__ = ['ContentExtractor']


class ContentExtractor:
    """Извлекает читаемый контент из HTML."""

    def __init__(self, min_text_length: int = 200) -> None:
        """Инициализировать экстрактор.

        Args:
            min_text_length: Минимальная длина текста для успешного извлечения.
        """
        self.min_text_length = min_text_length

    def extract(self, html: str, url: str) -> Article | None:
        """Извлечь статью из HTML.

        Args:
            html: HTML-код страницы.
            url: Исходный URL (для нормализации).

        Returns:
            Объект Article или None, если извлечь не удалось.
        """
        if not html or not html.strip():
            return None

        try:
            doc = readability.Document(html)
            content_html = doc.summary()
            title = doc.title()

            # Извлекаем чистый текст из HTML
            text = self._html_to_text(content_html)

            if len(text) < self.min_text_length:
                return None

            # Пытаемся найти автора
            author = self._extract_author(html)

            return Article(
                url=normalize_url(url),
                content=text,
                title=title or None,
                author=author,
            )

        except (ParserError, ValueError, TypeError):
            # Логирование будет в вызывающем коде
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
            # Если lxml не справился, убираем теги вручную
            text = self._strip_tags(html)

        # Нормализуем пробелы
        lines = (line.strip() for line in text.splitlines())
        chunks = (chunk.strip() for line in lines for chunk in line.split('  '))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text.strip()

    def _strip_tags(self, html: str) -> str:
        """Удалить HTML-теги из строки (запасной метод)."""
        import re
        # Убираем теги
        text = re.sub(r'<[^>]+>', ' ', html)
        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_author(self, html: str) -> str | None:
        """Попытаться извлечь автора из HTML.

        Args:
            html: HTML-код страницы.

        Returns:
            Имя автора или None.
        """
        # Простейшие эвристики — можно расширять
        patterns = [
            r'<meta[^>]+name="author"[^>]+content="([^"]+)"',
            r'<meta[^>]+property="article:author"[^>]+content="([^"]+)"',
            r'class="[^"]*author[^"]*"[^>]*>([^<]+)',
            r'class="[^"]*byline[^"]*"[^>]*>([^<]+)',
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None
