"""Извлечение основного контента из HTML-страниц.

Стратегия извлечения (waterfall):
1. readability-lxml — основной метод
2. JSON-LD ``articleBody`` — структурированные данные
3. ``<article>`` тег — прямой парсинг DOM

Если ни один метод не вернул достаточно текста,
возвращаем None.
"""

import json
import logging
import re

import lxml.html
import readability
from lxml.etree import ParserError

from bot.models.article import Article
from bot.utils.url_utils import normalize_url

__all__ = ['ContentExtractor']

logger = logging.getLogger(__name__)

_AUTHOR_PATTERNS: list[str] = [
    (
        r'<meta[^>]+name="author"'
        r'[^>]+content="([^"]+)"'
    ),
    (
        r'<meta[^>]+property="article:author"'
        r'[^>]+content="([^"]+)"'
    ),
    r'class="[^"]*author[^"]*"[^>]*>([^<]+)',
    r'class="[^"]*byline[^"]*"[^>]*>([^<]+)',
]

_TAG_RE = re.compile(r'<[^>]+>')
_JS_NOISE_RE = re.compile(
    r'if\s*\(typeof.*?\{[^}]*\}',
)

_DEFAULT_MIN_TEXT_LENGTH = 200


class ContentExtractor:
    """Извлекает читаемый контент из HTML."""

    def __init__(
        self,
        min_text_length: int = (
            _DEFAULT_MIN_TEXT_LENGTH
        ),
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

        Пробует три стратегии последовательно:
        readability → JSON-LD → <article> тег.

        Args:
            html: HTML-код страницы.
            url: Исходный URL (для нормализации).

        Returns:
            Article или None.
        """
        if not html or not html.strip():
            return None

        title = self._extract_title(html)
        author = self._extract_author(html)
        norm_url = normalize_url(url)

        # 1. readability-lxml (основной)
        text = self._try_readability(html, url)

        # 2. JSON-LD articleBody (fallback)
        if not text:
            text = self._try_json_ld(html, url)

        # 3. <article> тег (fallback)
        if not text:
            text = self._try_article_tag(html, url)

        if not text:
            logger.debug(
                'Все методы извлечения провалились'
                ' для %s',
                url,
            )
            return None

        return Article(
            url=norm_url,
            content=text,
            title=title,
            author=author,
        )

    def _try_readability(
        self,
        html: str,
        url: str,
    ) -> str | None:
        """Извлечь текст через readability-lxml.

        Args:
            html: HTML-код страницы.
            url: URL (для логов).

        Returns:
            Текст статьи или None.
        """
        try:
            doc = readability.Document(html)
            content_html = doc.summary()
            text = self._html_to_text(content_html)

            if len(text) >= self.min_text_length:
                return text

            logger.debug(
                'readability: текст слишком'
                ' короткий (%d) для %s',
                len(text),
                url,
            )
        except (
            ParserError,
            ValueError,
            TypeError,
        ):
            logger.debug(
                'readability: ошибка парсинга'
                ' для %s',
                url,
                exc_info=True,
            )
        return None

    def _try_json_ld(
        self,
        html: str,
        url: str,
    ) -> str | None:
        """Извлечь текст из JSON-LD articleBody.

        Многие новостные сайты встраивают полный
        текст статьи в структурированные данные
        ``<script type="application/ld+json">``.

        Args:
            html: HTML-код страницы.
            url: URL (для логов).

        Returns:
            Текст статьи или None.
        """
        try:
            tree = lxml.html.fromstring(html)
        except (ParserError, ValueError):
            return None

        for script in tree.xpath(
            '//script[@type="application/ld+json"]',
        ):
            if not script.text:
                continue
            try:
                data = json.loads(script.text)
            except (json.JSONDecodeError, ValueError):
                continue

            body = self._find_article_body(data)
            if (
                body
                and len(body) >= self.min_text_length
            ):
                logger.debug(
                    'json-ld: извлечено %d символов'
                    ' для %s',
                    len(body),
                    url,
                )
                return body

        return None

    def _find_article_body(
        self,
        data: object,
    ) -> str | None:
        """Рекурсивно найти articleBody в JSON-LD.

        JSON-LD может быть dict, list, или
        вложенная структура с ``@graph``.

        Args:
            data: Распарсенный JSON.

        Returns:
            Текст articleBody или None.
        """
        if isinstance(data, dict):
            if 'articleBody' in data:
                return str(data['articleBody'])
            if '@graph' in data:
                return self._find_article_body(
                    data['@graph'],
                )
        if isinstance(data, list):
            for item in data:
                result = self._find_article_body(
                    item,
                )
                if result:
                    return result
        return None

    def _try_article_tag(
        self,
        html: str,
        url: str,
    ) -> str | None:
        """Извлечь текст из ``<article>`` тега.

        Удаляет шумовые элементы (script, style,
        nav, footer) из ``<article>`` перед
        извлечением текста.

        Args:
            html: HTML-код страницы.
            url: URL (для логов).

        Returns:
            Текст статьи или None.
        """
        try:
            tree = lxml.html.fromstring(html)
        except (ParserError, ValueError):
            return None

        articles = tree.xpath('//article')
        if not articles:
            return None

        article_el = articles[0]
        for tag in article_el.xpath(
            './/script | .//style'
            ' | .//nav | .//footer',
        ):
            tag.getparent().remove(tag)

        text = article_el.text_content()
        text = self._clean_article_text(text)

        if len(text) >= self.min_text_length:
            logger.debug(
                'article-tag: извлечено %d символов'
                ' для %s',
                len(text),
                url,
            )
            return text

        return None

    def _extract_title(
        self,
        html: str,
    ) -> str | None:
        """Извлечь заголовок через readability.

        Args:
            html: HTML-код страницы.

        Returns:
            Заголовок или None.
        """
        try:
            doc = readability.Document(html)
            title = doc.title()
            return title if title else None
        except (
            ParserError,
            ValueError,
            TypeError,
        ):
            return None

    def _html_to_text(self, html: str) -> str:
        """Конвертировать HTML в чистый текст.

        Args:
            html: HTML-код.

        Returns:
            Чистый текст с нормализованными
            пробелами.
        """
        try:
            root = lxml.html.fromstring(html)
            text = root.text_content()
        except (ParserError, ValueError):
            text = self._strip_tags(html)

        return self._normalize_whitespace(text)

    @staticmethod
    def _clean_article_text(text: str) -> str:
        """Очистить текст из article-тега.

        Удаляет JS-шум и нормализует пробелы.

        Args:
            text: Сырой text_content().

        Returns:
            Очищенный текст.
        """
        text = _JS_NOISE_RE.sub('', text)
        return ContentExtractor._normalize_whitespace(
            text,
        )

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Нормализовать пробелы в тексте.

        Args:
            text: Сырой текст.

        Returns:
            Текст с нормализованными пробелами.
        """
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
        return _TAG_RE.sub('', html)

    @staticmethod
    def _extract_author(
        html: str,
    ) -> str | None:
        """Извлечь имя автора из HTML.

        Args:
            html: Полный HTML страницы.

        Returns:
            Имя автора или None.
        """
        for pattern in _AUTHOR_PATTERNS:
            match = re.search(
                pattern, html, re.IGNORECASE,
            )
            if match:
                author = match.group(1).strip()
                if author:
                    return author
        return None
