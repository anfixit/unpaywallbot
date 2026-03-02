"""Метод обхода metered paywall через подмену User-Agent на Googlebot.

Принцип работы: многие издания (NYT, многие метерные paywall)
отдают полный контент поисковым ботам для индексации.
Запрос с User-Agent Googlebot и Referer от Google получает полный текст.
"""

import random

import httpx

from bot.constants import DEFAULT_TIMEOUT_SECONDS
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_googlebot_spoof']

# База User-Agent'ов Googlebot (разные версии)
GOOGLEBOT_AGENTS = [
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    'Googlebot/2.1 (+http://www.google.com/bot.html)',
    'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/W.X.Y.Z Safari/537.36',
    'Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
]

# Рефереры от Google (для большей правдоподобности)
GOOGLE_REFERRERS = [
    'https://www.google.com/',
    'https://www.google.com/search?q=news',
    'https://www.google.com/search?q=article',
    'https://www.google.co.uk/',
    'https://www.google.de/',
]


def _get_random_googlebot_headers() -> dict[str, str]:
    """Сгенерировать случайные заголовки, имитирующие Googlebot."""
    return {
        'User-Agent': random.choice(GOOGLEBOT_AGENTS),
        'Referer': random.choice(GOOGLE_REFERRERS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }


async def fetch_via_googlebot_spoof(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Извлечь статью, маскируясь под Googlebot.

    Выполняет HTTP-запрос с заголовками Googlebot.
    Работает для сайтов с metered paywall, которые отдают
    контент поисковым ботам.

    Args:
        url: URL статьи.
        extractor: Экстрактор контента.
        client: HTTP-клиент.

    Returns:
        Объект Article или None, если не удалось извлечь.

    Raises:
        httpx.HTTPError: При проблемах с сетью.
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
        # Пробуем разные варианты заголовков (до 3 попыток)
        for attempt in range(3):
            headers = _get_random_googlebot_headers()

            response = await client.get(
                norm_url,
                headers=headers,
            )

            if response.status_code == 200:
                # Проверяем, что это HTML
                content_type = response.headers.get('content-type', '')
                if 'text/html' in content_type:
                    article = extractor.extract(response.text, norm_url)
                    if article and not article.is_empty:
                        return article

            # Если получили 403 или 429, возможно, нас раскусили
            if response.status_code in (403, 429):
                # Пробуем ещё раз с другими заголовками
                continue

            # Другие ошибки пробрасываем
            response.raise_for_status()

        return None

    finally:
        if close_client:
            await client.aclose()
