"""Получение публичного HTML с crawler User-Agent."""

import logging
import secrets

import httpx

from bot.constants import MAX_RETRY_COUNT, BypassMethod
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.services.http_client import create_safe_http_client
from bot.utils.url_utils import extract_domain, normalize_url

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
    """Сгенерировать crawler-заголовки."""
    return {
        'User-Agent': secrets.choice(
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
    """Попробовать получить публичную crawler-версию страницы."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    close_client = client is None
    if client is None:
        client = create_safe_http_client()

    if extractor is None:
        extractor = ContentExtractor()

    try:
        for attempt in range(MAX_RETRY_COUNT):
            response = await client.get(
                norm_url,
                headers=_get_random_googlebot_headers(),
            )

            if response.status_code == 200:
                content_type = response.headers.get(
                    'content-type',
                    '',
                ).lower()
                if 'text/html' in content_type:
                    article = extractor.extract(
                        response.text,
                        norm_url,
                    )
                    if article and not article.is_empty:
                        article.extraction_method = (
                            BypassMethod.GOOGLEBOT_SPOOF
                        )
                        return article

            if response.status_code in (403, 429):
                logger.debug(
                    'Crawler fetch %s: %d '
                    '(попытка %d/%d)',
                    extract_domain(norm_url),
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
