"""Метод обхода через archive.ph.

Принцип: archive.ph кеширует страницы без paywall.
Если архив есть — забираем. Если нет — запрашиваем
создание и ждём.
"""

import asyncio

import httpx

from bot.constants import DEFAULT_TIMEOUT_SECONDS
from bot.models.article import Article
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_archive']

_ARCHIVE_BASE = 'https://archive.ph'
_MAX_WAIT_SECONDS = 60
_POLL_INTERVAL = 5


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
        archive_url = f'{_ARCHIVE_BASE}/{norm_url}'

        response = await client.get(archive_url)

        if response.status_code == 200:
            article = extractor.extract(
                response.text, norm_url,
            )
            if article and not article.is_empty:
                return article

        # Архива нет — запрашиваем создание
        html = await _request_archive(
            client, norm_url,
        )
        if html:
            return extractor.extract(html, norm_url)

        return None

    finally:
        if close_client:
            await client.aclose()


async def _request_archive(
    client: httpx.AsyncClient,
    url: str,
) -> str | None:
    """Запросить создание архива и дождаться.

    Returns:
        HTML архивной страницы или None.
    """
    try:
        await client.post(
            f'{_ARCHIVE_BASE}/submit/',
            data={'url': url},
        )
    except httpx.HTTPError:
        return None

    archive_url = f'{_ARCHIVE_BASE}/{url}'
    polls = _MAX_WAIT_SECONDS // _POLL_INTERVAL

    for _ in range(polls):
        await asyncio.sleep(_POLL_INTERVAL)

        try:
            response = await client.get(archive_url)
            if response.status_code == 200:
                # «Waiting» — страница ожидания archive.ph
                if 'Waiting' not in response.text:
                    return response.text
        except httpx.HTTPError:
            continue

    return None
