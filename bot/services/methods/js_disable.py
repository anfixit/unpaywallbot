"""Метод обхода soft paywall через отключение JS.

Принцип: многие сайты отдают полный контент в HTML,
но скрывают его JS-оверлеем. HTTP-запрос без JS
возвращает чистый HTML.
"""

import httpx

from bot.constants import DEFAULT_TIMEOUT_SECONDS
from bot.models.article import Article
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_js_disable']

_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36'
)


async def fetch_via_js_disable(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Извлечь статью через отключение JavaScript.

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
        response = await client.get(
            norm_url,
            headers={
                'User-Agent': _DEFAULT_USER_AGENT,
                'Accept': (
                    'text/html,application/xhtml+xml'
                ),
            },
        )
        response.raise_for_status()

        content_type = response.headers.get(
            'content-type', '',
        )
        if 'text/html' not in content_type:
            return None

        return extractor.extract(
            response.text, norm_url,
        )

    finally:
        if close_client:
            await client.aclose()
