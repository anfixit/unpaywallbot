"""Метод обхода metered paywall через Googlebot spoof.

Принцип: сайты с metered paywall часто отдают полный
контент поисковым ботам (для индексации). Имитируем
заголовки Googlebot.
"""

import logging
import random

import httpx

from bot.constants import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RETRY_COUNT,
)
from bot.models.article import Article
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_googlebot_spoof']

logger = logging.getLogger(__name__)

_GOOGLEBOT_USER_AGENTS = [
    (
        'Mozilla/5.0 (compatible; Googlebot/2.1; '
        '+http://www.google.com/bot.html)'
    ),
    (
        'Mozilla/5.0 '
        '(Linux; Android 6.0.1; Nexus 5X) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/W.X.Y.Z Mobile Safari/537.36 '
        '(compatible; Googlebot/2.1; '
        '+http://www.google.com/bot.html)'
    ),
    (
        'Googlebot/2.1 '
        '(+http://www.google.com/bot.html)'
    ),
]


def _get_random_googlebot_headers() -> dict[str, str]:
    """Сгенерировать заголовки Googlebot."""
    return {
        'User-Agent': random.choice(
            _GOOGLEBOT_USER_AGENTS,
        ),
        'Accept': (
            'text/html,application/xhtml+xml'
        ),
        'Accept-Language': 'en-US,en;q=0.5',
        'From': 'googlebot(at)googlebot.com',
    }


async def fetch_via_googlebot_spoof(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Извлечь статью через Googlebot spoof.

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
        for attempt in range(MAX_RETRY_COUNT):
            headers = _get_random_googlebot_headers()

            response = await client.get(
                norm_url, headers=headers,
            )

            if response.status_code == 200:
                content_type = response.headers.get(
                    'content-type', '',
                )
                if 'text/html' in content_type:
                    article = extractor.extract(
                        response.text, norm_url,
                    )
                    if article and not article.is_empty:
                        return article

            # 403/429 — нас раскусили, пробуем ещё
            if response.status_code in (403, 429):
                logger.debug(
                    'Googlebot spoof %s: %d '
                    '(попытка %d/%d)',
                    norm_url,
                    response.status_code,
                    attempt + 1,
                    MAX_RETRY_COUNT,
                )
                continue

            response.raise_for_status()

        return None

    finally:
        if close_client:
            await client.aclose()
