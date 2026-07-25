"""Получение статьи из существующего снимка archive.ph."""

import asyncio
import logging

import httpx

from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.services.http_client import create_safe_http_client
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_archive']

logger = logging.getLogger(__name__)

_ARCHIVE_BASE = 'https://archive.ph'
_MAX_WAIT_SECONDS = 60
_POLL_INTERVAL = 5
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
    """Получить публичный снимок страницы из archive.ph."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    close_client = client is None
    if client is None:
        client = create_safe_http_client()

    if extractor is None:
        extractor = ContentExtractor()

    try:
        newest_url = f'{_ARCHIVE_BASE}/newest/{norm_url}'
        try:
            response = await client.get(newest_url)
        except httpx.HTTPError:
            logger.debug(
                'archive.ph недоступен для %s',
                norm_url,
            )
            return None

        if response.status_code == 200:
            if not _is_wait_page(response.text):
                article = extractor.extract(
                    response.text,
                    norm_url,
                )
                if article and not article.is_empty:
                    logger.info(
                        'archive.ph: найден снимок '
                        'для %s (%d символов)',
                        norm_url,
                        len(article.content),
                    )
                    return article

        logger.info(
            'archive.ph: запрашиваем снимок для %s',
            norm_url,
        )
        archive_url = await _submit_and_wait(
            client,
            norm_url,
        )
        if not archive_url:
            return None

        try:
            response = await client.get(archive_url)
        except httpx.HTTPError:
            return None

        if response.status_code != 200:
            return None

        article = extractor.extract(
            response.text,
            norm_url,
        )
        if article and not article.is_empty:
            logger.info(
                'archive.ph: получен снимок '
                'для %s (%d символов)',
                norm_url,
                len(article.content),
            )
            return article

        return None
    finally:
        if close_client:
            await client.aclose()


def _is_wait_page(html: str) -> bool:
    """Проверить, является ли страница ожиданием."""
    return any(marker in html for marker in _WAIT_MARKERS)


async def _submit_and_wait(
    client: httpx.AsyncClient,
    url: str,
) -> str | None:
    """Запросить снимок и дождаться его появления."""
    try:
        response = await client.post(
            f'{_ARCHIVE_BASE}/submit/',
            data={'url': url},
            headers={
                'Content-Type': (
                    'application/x-www-form-urlencoded'
                ),
            },
        )
        if response.status_code in (301, 302):
            location = response.headers.get(
                'location',
                '',
            )
            if location:
                return location
    except httpx.HTTPError:
        logger.debug(
            'archive.ph submit не удался для %s',
            url,
        )
        return None

    newest_url = f'{_ARCHIVE_BASE}/newest/{url}'
    polls = _MAX_WAIT_SECONDS // _POLL_INTERVAL

    for attempt in range(polls):
        await asyncio.sleep(_POLL_INTERVAL)

        try:
            response = await client.get(newest_url)
            if (
                response.status_code == 200
                and not _is_wait_page(response.text)
            ):
                return str(response.url)
        except httpx.HTTPError:
            continue

        logger.debug(
            'archive.ph poll %d/%d для %s',
            attempt + 1,
            polls,
            url,
        )

    logger.warning(
        'archive.ph: таймаут создания для %s',
        url,
    )
    return None
