"""Read an existing public snapshot from archive.ph."""

import logging

import httpx

from bot.constants import BypassMethod
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.services.http_client import create_safe_http_client
from bot.utils.url_utils import extract_domain, normalize_url

__all__ = ['fetch_via_archive']

logger = logging.getLogger(__name__)

_ARCHIVE_BASE = 'https://archive.ph'

# Архив блокирует часть хостингов целиком. Без
# отдельного лимита на соединение каждая попытка
# съедает десятки секунд из бюджета запроса.
_ARCHIVE_CONNECT_TIMEOUT = 5.0
_ARCHIVE_TOTAL_TIMEOUT = 20.0
_WAIT_MARKERS = (
    'Saving page',
    'Webpage capture',
    'Waiting',
    'Just a moment',
)


async def fetch_via_archive(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Получить только уже существующий публичный снимок."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    close_client = client is None
    if client is None:
        client = create_safe_http_client(
            timeout_seconds=_ARCHIVE_TOTAL_TIMEOUT,
            connect_timeout_seconds=_ARCHIVE_CONNECT_TIMEOUT,
        )

    if extractor is None:
        extractor = ContentExtractor()

    try:
        newest_url = f'{_ARCHIVE_BASE}/newest/{norm_url}'
        try:
            response = await client.get(newest_url)
        except httpx.HTTPError:
            logger.debug(
                'archive.ph недоступен для %s',
                extract_domain(norm_url),
            )
            return None

        if response.status_code != 200:
            return None
        if _is_wait_page(response.text):
            return None

        article = extractor.extract(
            response.text,
            norm_url,
        )
        if not article or article.is_empty:
            return None

        article.extraction_method = BypassMethod.ARCHIVE_RELAY
        logger.info(
            'archive.ph: найден снимок для %s (%d символов)',
            extract_domain(norm_url),
            len(article.content),
        )
        return article
    finally:
        if close_client:
            await client.aclose()


def _is_wait_page(html: str) -> bool:
    """Проверить, является ли страница ожиданием."""
    return any(marker in html for marker in _WAIT_MARKERS)
