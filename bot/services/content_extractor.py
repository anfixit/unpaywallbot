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
    'Diesen Artikel',
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
    'WELTplus',
    'Bereits Abonnent',
    'Alle WELTplus Inhalte',
    'Jetzt testen',
]

# Маркеры обрезки — если найдены, значит текст
# обрезан paywall (добавляем пометку).
_TRUNCATION_MARKERS: list[str] = [
    'Den ganzen Text lesen Sie hier',
    'Lesen Sie mehr',
    'Weiterlesen mit',
    'Jetzt weiterlesen',
    'Read more',
    'Continue reading',
    'Subscribe to read',
    'To continue reading',
]

# Текст короче этого порога с 2+ маркерами —
# чистое промо (не статья).
_PROMO_THRESHOLD = 1500

_DEFAULT_MIN_TEXT_LENGTH = 200

# Блочные теги — перед ними вставляем \n\n.
_BLOCK_TAGS = frozenset({
    'p', 'div', 'h1', 'h2', 'h3', 'h4',
    'h5', 'h6', 'li', 'blockquote', 'br',
    'tr', 'section', 'figcaption', 'header',
    'article', 'main',
})

# Теги-мусор, удаляем перед экстракцией.
_NOISE_TAGS = frozenset({
    'script', 'style', 'nav', 'footer',
    'aside', 'noscript', 'iframe',
    'svg', 'form', 'button', 'figure',
})

# CSS-классы, указывающие на мусорные блоки.
_NOISE_CLASS_PATTERNS = re.compile(
    r'paywall|newsletter|subscribe|social'
    r'|share|comment|related|sidebar|ad-'
    r'|banner|promo|overlay|abo-|premium'
    r'|offer|conversion|regwall|gate'
    r'|piano-|plenigo|paywall-portal',
    re.IGNORECASE,
)

# Regex для мусорных строк: кнопки шаринга,
# подписи к фото, AI-дисклеймеры.
# Применяется к каждому абзацу после экстракции.
_JUNK_LINE_RE = re.compile(
    r'^('
    r'X\.com|Facebook|E-Mail|Messenger'
    r'|WhatsApp|Telegram|LinkedIn|Pocket'
    r'|Flipboard|Pinterest|Twitter'
    r'|Reddit|Xing'
    r')$',
)

_JUNK_FRAGMENT_RE = re.compile(
    r'^(?:'
    r'Foto:\s.*'
    r'|Photo:\s.*'
    r'|Bild:\s.*'
    r'|Quelle:\s.*'
    r'|Automatisch erstellt mit KI.*'
    r'|Mehr Informationen dazu.*'
    r'|War die Zusammenfassung hilfreich\??'
    r'|Danke f.r Ihr Feedback!?'
    r'|hier\.'
    r'|Von'
    r'|aus'
    r'|\u00a9\s.*'
    r'|DER SPIEGEL \d+/\d+'
    r'|\d{2}\.\d{2}\.\d{4}'
    r',\s*\d{2}[\.:]\d{2}\s*Uhr'
    r'|\u2022'
    r')$',
)


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

        # Пометить, если текст обрезан paywall
        if self._is_truncated(text):
            text = self._strip_truncation_tail(text)
            text += (
                '\n\n'
                '--- Текст обрезан paywall. '
                'Показана бесплатная часть. ---'
            )

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
        self._remove_noise(article_el)

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
    def _remove_noise(
        element: lxml.html.HtmlElement,
    ) -> None:
        """Удалить шумовые элементы из дерева.

        Удаляет: script, style, nav, footer, aside,
        а также элементы с мусорными CSS-классами
        (paywall-overlay, subscribe-блоки и т.п.).

        Args:
            element: HTML-элемент.
        """
        # Удаляем по тегам
        noise_xpath = ' | '.join(
            f'.//{tag}' for tag in _NOISE_TAGS
        )
        for tag in element.xpath(noise_xpath):
            parent = tag.getparent()
            if parent is not None:
                parent.remove(tag)

        # Удаляем по CSS-классам
        for el in element.xpath('.//*[@class]'):
            cls = el.get('class', '')
            if _NOISE_CLASS_PATTERNS.search(cls):
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)

        # Удаляем по data-атрибутам (paywall-
        # порталы: piano, plenigo, споты и т.п.)
        for el in element.xpath(
            './/*[@data-piano-id]'
            ' | .//*[@data-plenigo-id]'
            ' | .//*[@data-paywall]'
            ' | .//*[contains(@class, "abo")]'
            ' | .//*[contains(@id, "paywall")]'
            ' | .//*[contains(@id, "piano")]'
        ):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    @staticmethod
    def _is_paywall_promo(text: str) -> bool:
        """Проверить, является ли текст промо.

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

    @staticmethod
    def _is_truncated(text: str) -> bool:
        """Проверить, обрезан ли текст paywall.

        Args:
            text: Извлечённый текст.

        Returns:
            True если найден маркер обрезки.
        """
        lower = text.lower()
        return any(
            marker.lower() in lower
            for marker in _TRUNCATION_MARKERS
        )

    @staticmethod
    def _strip_truncation_tail(text: str) -> str:
        """Убрать хвост с маркером обрезки.

        Ищет маркер обрезки и обрезает текст
        перед ним.

        Args:
            text: Текст с маркером.

        Returns:
            Текст без маркера обрезки.
        """
        lower = text.lower()
        earliest_pos = len(text)
        for marker in _TRUNCATION_MARKERS:
            pos = lower.find(marker.lower())
            if pos != -1 and pos < earliest_pos:
                earliest_pos = pos

        if earliest_pos < len(text):
            return text[:earliest_pos].rstrip()
        return text

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

        Вставляет \\n\\n перед блочными тегами
        и после ``<br>``. Обрабатывает
        ``<strong>``/``<b>`` как подзаголовки
        когда они — единственный ребёнок ``<p>``
        (типичный паттерн Spiegel, Zeit и др.).

        Args:
            element: HTML-элемент (lxml).

        Returns:
            Текст с абзацами.
        """
        parts: list[str] = []

        for node in element.iter():
            tag = node.tag if isinstance(
                node.tag, str,
            ) else ''

            # Блочный тег -> разделитель
            if tag in _BLOCK_TAGS:
                parts.append('\n\n')

            # <strong>/<b> как единственный ребёнок
            # <p> -> подзаголовок (DE-стиль).
            # Без этого «Übereinander gestapelte
            # SärgeArchäologen» слипается.
            if tag in ('strong', 'b'):
                parent = node.getparent()
                if (
                    parent is not None
                    and parent.tag == 'p'
                    and len(parent) == 1
                    and not (
                        parent.text or ''
                    ).strip()
                ):
                    parts.append('\n\n')

            if node.text:
                parts.append(node.text)

            # <br> -> одинарный перенос
            if tag == 'br':
                parts.append('\n')

            if node.tail:
                parts.append(node.tail)

        return ''.join(parts)

    @staticmethod
    def _clean_article_text(text: str) -> str:
        """Очистить текст из article-тега.

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
        lines = []
        for line in text.splitlines():
            cleaned = ' '.join(line.split())
            lines.append(cleaned)

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

        paragraphs = [
            para.strip()
            for para in '\n'.join(result).split(
                '\n\n',
            )
            if para.strip()
        ]

        # Убираем мусорные абзацы: кнопки
        # шаринга, подписи к фото, даты
        cleaned = [
            p for p in paragraphs
            if not _JUNK_LINE_RE.match(p)
            and not _JUNK_FRAGMENT_RE.match(p)
        ]

        return '\n\n'.join(cleaned)

    @staticmethod
    def _strip_tags(html: str) -> str:
        """Удалить HTML-теги (запасной метод)."""
        return _TAG_RE.sub('', html)

    @staticmethod
    def _extract_author(
        html: str,
    ) -> str | None:
        """Извлечь имя автора из HTML.

        Фильтрует мусор: URL, «Von», «aus»,
        слишком короткие значения.

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
                if not author:
                    continue
                # URL — не автор
                if author.startswith(('http', '/')):
                    continue
                # Слишком короткие / мусорные
                if author.lower() in (
                    'von', 'aus', 'by', 'author',
                    'redaktion', 'admin',
                ):
                    continue
                # Минимум 3 символа
                if len(author) < 3:
                    continue
                return author
        return None
