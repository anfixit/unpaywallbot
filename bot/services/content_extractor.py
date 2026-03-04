"""Извлечение основного контента из HTML-страниц.

Стратегия извлечения:
1. readability-lxml
2. JSON-LD ``articleBody``
3. ``<article>`` тег

Все три стратегии запускаются, выбирается самый
длинный результат — он ближе к полному тексту.
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

# Маркеры paywall-промо в извлечённом тексте.
_PAYWALL_MARKERS: list[str] = [
    'weiterlesen mit SPIEGEL+',
    'Diesen Artikel weiterlesen',
    'Sie können den Artikel leider nicht',
    'Jetzt abonnieren',
    'Freier Zugriff auf alle S+-Artikel',
    'Freier Zugriff auf alle Z+-Artikel',
    'Jetzt 30 Tage gratis testen',
    'Digital-Abo',
    'Artikel freischalten',
    'Premium-Abo',
    'exklusiv für Abonnenten',
    'subscribe to continue',
    'subscribers only',
    'to read this article',
    'Zugang zu allen Artikeln',
]

# Текст короче этого порога с 2+ маркерами —
# чистое промо (не статья).
_PROMO_THRESHOLD = 1500

_DEFAULT_MIN_TEXT_LENGTH = 200

# Блочные теги, после которых нужен перенос строки.
_BLOCK_TAGS = frozenset({
    'p', 'div', 'h1', 'h2', 'h3', 'h4',
    'h5', 'h6', 'li', 'blockquote', 'br',
    'tr', 'section', 'figcaption',
})

# Теги-мусор, которые удаляем перед экстракцией.
_NOISE_TAGS = frozenset({
    'script', 'style', 'nav', 'footer',
    'aside', 'noscript', 'iframe',
    'svg', 'form', 'button',
})


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
            min_text_length: Минимальная длина
                для успешного извлечения.
        """
        self.min_text_length = min_text_length

    def extract(
        self,
        html: str,
        url: str,
    ) -> Article | None:
        """Извлечь статью из HTML.

        Запускает все три стратегии, выбирает
        самый длинный результат.

        Args:
            html: HTML-код страницы.
            url: Исходный URL.

        Returns:
            Article или None.
        """
        if not html or not html.strip():
            return None

        title = self._extract_title(html)
        author = self._extract_author(html)
        norm_url = normalize_url(url)

        candidates: list[str] = []

        readability_text = self._try_readability(
            html, url,
        )
        if readability_text:
            candidates.append(readability_text)

        json_ld_text = self._try_json_ld(html, url)
        if json_ld_text:
            candidates.append(json_ld_text)

        article_text = self._try_article_tag(
            html, url,
        )
        if article_text:
            candidates.append(article_text)

        if not candidates:
            logger.debug(
                'Все методы извлечения провалились'
                ' для %s',
                url,
            )
            return None

        text = max(candidates, key=len)

        if self._is_paywall_promo(text):
            logger.debug(
                'Текст является paywall-промо'
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
            except (
                json.JSONDecodeError,
                ValueError,
            ):
                continue

            body = self._find_article_body(data)
            if (
                body
                and len(body)
                >= self.min_text_length
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

        Удаляет шумовые элементы, сохраняет
        абзацную структуру.

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

        # Удаляем шумовые элементы
        noise_xpath = ' | '.join(
            f'.//{tag}' for tag in _NOISE_TAGS
        )
        for tag in article_el.xpath(noise_xpath):
            parent = tag.getparent()
            if parent is not None:
                parent.remove(tag)

        text = self._element_to_text(article_el)
        text = self._clean_article_text(text)

        if len(text) >= self.min_text_length:
            logger.debug(
                'article-tag: извлечено %d '
                'символов для %s',
                len(text),
                url,
            )
            return text

        return None

    @staticmethod
    def _is_paywall_promo(text: str) -> bool:
        """Проверить, является ли текст промо.

        Текст считается промо только если маркеры
        занимают значительную часть контента.
        Короткий текст с 2+ маркерами — промо.
        Длинный текст с маркерами — статья
        с paywall-виджетом, не отвергаем.

        Args:
            text: Извлечённый текст.

        Returns:
            True если текст — paywall-промо.
        """
        marker_count = sum(
            1
            for marker in _PAYWALL_MARKERS
            if marker.lower() in text.lower()
        )
        if marker_count < 2:
            return False
        return len(text) < _PROMO_THRESHOLD

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
        """Конвертировать HTML в текст с абзацами.

        Сохраняет структуру параграфов: блочные
        теги (p, h1-h6, div, li) разделяются
        двойным переносом строки.

        Args:
            html: HTML-код.

        Returns:
            Текст с абзацами.
        """
        try:
            root = lxml.html.fromstring(html)
            text = self._element_to_text(root)
        except (ParserError, ValueError):
            text = self._strip_tags(html)

        return self._normalize_paragraphs(text)

    @staticmethod
    def _element_to_text(
        element: lxml.html.HtmlElement,
    ) -> str:
        """Извлечь текст из элемента с абзацами.

        Вставляет разделитель \\n\\n после блочных
        тегов (p, div, h1-h6, li...), чтобы
        сохранить визуальную структуру статьи.

        Args:
            element: HTML-элемент (lxml).

        Returns:
            Текст с абзацами.
        """
        parts: list[str] = []

        for node in element.iter():
            # Вставляем разделитель перед блочным
            if node.tag in _BLOCK_TAGS:
                parts.append('\n\n')

            if node.text:
                parts.append(node.text)

            if node.tail:
                parts.append(node.tail)

        return ''.join(parts)

    @staticmethod
    def _clean_article_text(text: str) -> str:
        """Очистить текст из article-тега.

        Удаляет JS-шум и нормализует абзацы.

        Args:
            text: Сырой text.

        Returns:
            Очищенный текст.
        """
        text = _JS_NOISE_RE.sub('', text)
        return ContentExtractor._normalize_paragraphs(
            text,
        )

    @staticmethod
    def _normalize_paragraphs(text: str) -> str:
        """Нормализовать абзацы в тексте.

        Схлопывает множественные пустые строки
        в одну, убирает пробелы в начале/конце
        строк, но сохраняет абзацную структуру.

        Args:
            text: Сырой текст.

        Returns:
            Текст с чистыми абзацами.
        """
        # Убираем пробелы внутри строк
        lines = []
        for line in text.splitlines():
            cleaned = ' '.join(line.split())
            lines.append(cleaned)

        # Схлопываем пустые строки (3+ -> 2)
        result: list[str] = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    result.append('')
                prev_empty = True
            else:
                result.append(line)
                prev_empty = False

        return '\n\n'.join(
            para.strip()
            for para in '\n'.join(result).split(
                '\n\n',
            )
            if para.strip()
        )

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
