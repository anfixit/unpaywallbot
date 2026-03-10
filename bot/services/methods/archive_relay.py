"""Метод обхода через archive.ph.

Принцип: archive.ph кеширует страницы без paywall.
Flow:
1. GET /newest/{url} — ищем существующий снимок
2. Если 404 — POST /submit/ для создания нового
3. Поллим /newest/{url} пока не появится

Важно: archive.ph может быть недоступен из
некоторых стран (РФ) — на DE-сервере работает.
"""

import asyncio
import logging

import httpx

from bot.constants import DEFAULT_TIMEOUT_SECONDS
from bot.models.article import Article
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_archive']

logger = logging.getLogger(__name__)

_ARCHIVE_BASE = 'https://archive.ph'
_MAX_WAIT_SECONDS = 60
_POLL_INTERVAL = 5

# archive.ph отдаёт «Saving page» или «Webpage
# capture» когда снимок ещё создаётся.
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
    """Извлечь статью через archive.ph.

    Args:
        url: URL статьи.
        extractor: Экстрактор контента.
        client: HTTP-клиент.

    Returns:
        Article или None.
    """
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    close_client = False
    if client is None:
        client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        close_client = True

    if extractor is None:
        extractor = ContentExtractor()

    try:
        # 1. Ищем существующий снимок
        newest_url = (
            f'{_ARCHIVE_BASE}/newest/{norm_url}'
        )
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
                    response.text, norm_url,
                )
                if article and not article.is_empty:
                    logger.info(
                        'archive.ph: найден снимок'
                        ' для %s (%d символов)',
                        norm_url,
                        len(article.content),
                    )
                    return article

        # 2. Снимка нет → создаём через POST
        logger.info(
            'archive.ph: создаём снимок для %s',
            norm_url,
        )
        archive_url = await _submit_and_wait(
            client, norm_url,
        )
        if not archive_url:
            return None

        # 3. Забираем готовый снимок
        try:
            response = await client.get(
                archive_url,
            )
        except httpx.HTTPError:
            return None

        if response.status_code != 200:
            return None

        article = extractor.extract(
            response.text, norm_url,
        )
        if article and not article.is_empty:
            logger.info(
                'archive.ph: создан снимок'
                ' для %s (%d символов)',
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
    return any(
        marker in html for marker in _WAIT_MARKERS
    )


async def _submit_and_wait(
    client: httpx.AsyncClient,
    url: str,
) -> str | None:
    """Запросить создание снимка и дождаться.

    POST на /submit/ инициирует создание.
    Потом поллим /newest/{url} пока не появится.

    Args:
        client: HTTP-клиент.
        url: URL для архивации.

    Returns:
        URL архивной страницы или None.
    """
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
        # archive.ph может вернуть redirect
        # на готовый снимок
        if response.status_code in (301, 302):
            location = response.headers.get(
                'location', '',
            )
            if location:
                return location
    except httpx.HTTPError:
        logger.debug(
            'archive.ph submit не удался для %s',
            url,
        )
        return None

    # Поллим /newest/ пока снимок не появится
    newest_url = f'{_ARCHIVE_BASE}/newest/{url}'
    polls = _MAX_WAIT_SECONDS // _POLL_INTERVAL

    for attempt in range(polls):
        await asyncio.sleep(_POLL_INTERVAL)

        try:
            response = await client.get(newest_url)
            if response.status_code == 200:
                if not _is_wait_page(response.text):
                    # Вернём финальный URL
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
