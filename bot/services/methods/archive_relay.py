"""Метод обхода через archive.ph (универсальный fallback).

Отправляет URL в archive.ph, ждёт сохранения и возвращает
архивную копию. Работает для любых типов paywall, но медленно
(10-30 сек) и не гарантирует наличие свежих статей.
"""

import asyncio

import httpx

from bot.constants import DEFAULT_TIMEOUT_SECONDS
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_archive']

# API archive.ph (неофициальный, но стабильный)
ARCHIVE_API_URL = 'https://archive.ph/'

# Максимальное время ожидания архивации
MAX_WAIT_SECONDS = 30
# Интервал между проверками
POLL_INTERVAL = 2


async def fetch_via_archive(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Извлечь статью через archive.ph.

    Отправляет URL в архив, ждёт создания копии и парсит её.

    Args:
        url: URL статьи.
        extractor: Экстрактор контента.
        client: HTTP-клиент.

    Returns:
        Объект Article или None, если не удалось.
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
        # 1. Запрашиваем архивацию
        archive_url = await _submit_to_archive(client, norm_url)
        if not archive_url:
            return None

        # 2. Ждём, пока архив создастся
        archived_page = await _wait_for_archive(client, archive_url)
        if not archived_page:
            return None

        # 3. Извлекаем контент из архивной копии
        article = extractor.extract(archived_page, norm_url)

        return article

    finally:
        if close_client:
            await client.aclose()


async def _submit_to_archive(client: httpx.AsyncClient, url: str) -> str | None:
    """Отправить URL в archive.ph и получить ссылку на архив."""
    try:
        # Простая форма: POST с url=...
        response = await client.post(
            ARCHIVE_API_URL,
            data={'url': url},
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ArchiveBot)',
            }
        )
        response.raise_for_status()

        # archive.ph возвращает 200 и ссылку в Location или в теле
        # Пробуем найти ссылку на архив
        if 'location' in response.headers:
            return response.headers['location']

        # Если нет Location, ищем в теле страницы
        # (упрощённо — возвращаем None, в реальном проекте нужен парсинг)
        return None

    except httpx.HTTPError:
        return None


async def _wait_for_archive(client: httpx.AsyncClient, archive_url: str) -> str | None:
    """Дождаться создания архивной копии и вернуть HTML."""
    for attempt in range(MAX_WAIT_SECONDS // POLL_INTERVAL):
        await asyncio.sleep(POLL_INTERVAL)

        try:
            response = await client.get(archive_url)
            if response.status_code == 200:
                # Проверяем, что это не страница ожидания
                if 'Waiting' not in response.text:
                    return response.text
        except httpx.HTTPError:
            continue

    return None
