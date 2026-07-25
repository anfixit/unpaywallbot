"""Получение публичной версии страницы WSJ."""

import logging
import re

import httpx

from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.services.http_client import create_safe_http_client
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
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

_WSJ_HEADERS_GOOGLE: dict[str, str] = {
    'User-Agent': (
        'Mozilla/5.0 (compatible; '
        'Googlebot/2.1; '
        '+http://www.google.com/bot.html)'
    ),
    'Referer': _GOOGLE_REFERER,
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

_WSJ_ARTICLE_RE = re.compile(
    r'wsj\.com/articles/(.+)',
)
_WSJ_PATH_RE = re.compile(
    r'wsj\.com(/[^?#]+)',
)


def _build_rsswn_url(url: str) -> str:
    """Добавить параметр ``mod=rsswn``."""
    if 'mod=rsswn' in url:
        return url
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}mod=rsswn'


def _build_amp_url(url: str) -> str | None:
    """Построить AMP-вариант URL статьи."""
    match = _WSJ_ARTICLE_RE.search(url)
    if match:
        slug = match.group(1).split('?')[0]
        return (
            'https://www.wsj.com'
            f'/amp/articles/{slug}'
        )

    match = _WSJ_PATH_RE.search(url)
    if match:
        path = match.group(1).split('?')[0]
        return f'https://www.wsj.com/amp{path}'

    return None


async def fetch_via_wsj(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Попробовать получить публичные варианты страницы WSJ."""
    if extractor is None:
        extractor = ContentExtractor()

    norm_url = normalize_url(url)
    if not norm_url:
        return None

    article = await _try_fetch(
        _build_rsswn_url(norm_url),
        headers=_WSJ_HEADERS_FACEBOOK,
        extractor=extractor,
        client=client,
        label='facebook+rsswn',
    )
    if article:
        return article

    article = await _try_fetch(
        _build_rsswn_url(norm_url),
        headers=_WSJ_HEADERS_GOOGLE,
        extractor=extractor,
        client=client,
        label='googlebot+rsswn',
    )
    if article:
        return article

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
    """Попробовать один вариант загрузки."""
    own_client = client is None
    if client is None:
        client = create_safe_http_client()

    try:
        response = await client.get(
            url,
            headers=headers,
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
            'content-type',
            '',
        ).lower()
        if 'text/html' not in content_type:
            return None

        article = extractor.extract(
            response.text,
            url,
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
