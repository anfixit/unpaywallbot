"""Метод обхода WSJ paywall через AMP и Referer.

Принцип работы (из BPW Chrome Extension):
1. Добавляем ``?mod=rsswn`` — WSJ считает переход
   из RSS-ридера и ослабляет paywall
2. Ставим ``Referer: https://www.facebook.com`` —
   WSJ отдаёт полный текст для Facebook-трафика
3. Fallback: AMP-версия (``/amp/articles/...``)
   отдаёт контент без JS-paywall

Источник: bypass-paywalls-chrome, userscript
Andrea Lazzarotto.
"""

import logging
import re

import httpx

from bot.constants import DEFAULT_TIMEOUT_SECONDS
from bot.models.article import Article
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_wsj']

logger = logging.getLogger(__name__)

_FACEBOOK_REFERER = 'https://www.facebook.com'
_GOOGLE_REFERER = 'https://www.google.com'

_WSJ_HEADERS_FACEBOOK: dict[str, str] = {
    'User-Agent': (
        'facebookexternalhit/1.1 '
        '(+http://www.facebook.com/'
        'externalhit_uatext.php)'
    ),
    'Referer': _FACEBOOK_REFERER,
    'Accept': (
        'text/html,application/xhtml+xml'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

_WSJ_HEADERS_GOOGLE: dict[str, str] = {
    'User-Agent': (
        'Mozilla/5.0 (compatible; '
        'Googlebot/2.1; '
        '+http://www.google.com/bot.html)'
    ),
    'Referer': _GOOGLE_REFERER,
    'Accept': (
        'text/html,application/xhtml+xml'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

# Паттерн WSJ-статьи для построения AMP URL.
_WSJ_ARTICLE_RE = re.compile(
    r'wsj\.com/articles/(.+)',
)


def _build_rsswn_url(url: str) -> str:
    """Добавить ``?mod=rsswn`` к URL.

    Args:
        url: Оригинальный WSJ URL.

    Returns:
        URL с параметром mod=rsswn.
    """
    if 'mod=rsswn' in url:
        return url
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}mod=rsswn'


def _build_amp_url(url: str) -> str | None:
    """Построить AMP-версию WSJ URL.

    ``https://wsj.com/articles/slug``
    → ``https://wsj.com/amp/articles/slug``

    Args:
        url: Оригинальный WSJ URL.

    Returns:
        AMP URL или None если не статья.
    """
    match = _WSJ_ARTICLE_RE.search(url)
    if not match:
        return None
    slug = match.group(1)
    # Убираем query params из slug
    slug = slug.split('?')[0]
    return f'https://www.wsj.com/amp/articles/{slug}'


async def fetch_via_wsj(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Извлечь статью WSJ через цепочку методов.

    Цепочка: Facebook referer + rsswn →
    Google referer + rsswn → AMP-версия.

    Args:
        url: URL статьи на wsj.com.
        extractor: Экстрактор контента.
        client: HTTP-клиент (для тестов).

    Returns:
        Article или None.
    """
    if extractor is None:
        extractor = ContentExtractor()

    norm_url = normalize_url(url)

    # Шаг 1: Facebook referer + ?mod=rsswn
    article = await _try_fetch(
        _build_rsswn_url(norm_url),
        headers=_WSJ_HEADERS_FACEBOOK,
        extractor=extractor,
        client=client,
        label='facebook+rsswn',
    )
    if article:
        return article

    # Шаг 2: Googlebot + ?mod=rsswn
    article = await _try_fetch(
        _build_rsswn_url(norm_url),
        headers=_WSJ_HEADERS_GOOGLE,
        extractor=extractor,
        client=client,
        label='googlebot+rsswn',
    )
    if article:
        return article

    # Шаг 3: AMP-версия
    amp_url = _build_amp_url(norm_url)
    if amp_url:
        article = await _try_fetch(
            amp_url,
            headers=_WSJ_HEADERS_FACEBOOK,
            extractor=extractor,
            client=client,
            label='amp',
        )
        if article:
            return article

    logger.info('Все WSJ-методы не сработали: %s', url)
    return None


async def _try_fetch(
    url: str,
    headers: dict[str, str],
    extractor: ContentExtractor,
    client: httpx.AsyncClient | None,
    label: str,
) -> Article | None:
    """Попробовать один метод извлечения.

    Args:
        url: URL для запроса.
        headers: HTTP-заголовки.
        extractor: Экстрактор контента.
        client: HTTP-клиент.
        label: Метка для логов.

    Returns:
        Article или None.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    try:
        response = await client.get(
            url, headers=headers,
        )

        if response.status_code != 200:
            logger.debug(
                'WSJ %s: HTTP %d для %s',
                label,
                response.status_code,
                url,
            )
            return None

        content_type = response.headers.get(
            'content-type', '',
        )
        if 'text/html' not in content_type:
            return None

        article = extractor.extract(
            response.text, url,
        )
        if article and not article.is_empty:
            logger.info(
                'WSJ %s: извлечено %d символов',
                label,
                len(article.content),
            )
            return article

        return None

    except httpx.HTTPError:
        logger.debug(
            'WSJ %s: ошибка для %s',
            label,
            url,
            exc_info=True,
        )
        return None

    finally:
        if own_client:
            await client.aclose()
