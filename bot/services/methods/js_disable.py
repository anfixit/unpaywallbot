"""Метод обхода soft paywall через отключение JavaScript.

Принцип работы: многие сайты (Telegraph, немецкие freemium)
отдают полный контент в HTML, но скрывают его JS-оверлеем.
Простой HTTP-запрос без выполнения JS возвращает чистый HTML.
"""


import httpx

from bot.constants import DEFAULT_TIMEOUT_SECONDS
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_js_disable']


async def fetch_via_js_disable(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Извлечь статью через отключение JavaScript.

    Выполняет обычный HTTP-запрос (без JS) и парсит HTML.
    Работает для сайтов, где контент уже присутствует в DOM.

    Args:
        url: URL статьи.
        extractor: Экстрактор контента (если None, создаётся новый).
        client: HTTP-клиент (если None, создаётся временный).

    Returns:
        Объект Article или None, если не удалось извлечь.

    Raises:
        httpx.HTTPError: При проблемах с сетью (таймаут, 4xx/5xx).
    """
    # Нормализуем URL
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    # Создаём клиент, если не передан
    close_client = False
    if client is None:
        client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        close_client = True

    # Создаём экстрактор, если не передан
    if extractor is None:
        extractor = ContentExtractor()

    try:
        # Простой GET-запрос (без JS, без спец. заголовков)
        response = await client.get(
            norm_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
            }
        )
        response.raise_for_status()

        # Проверяем, что это HTML
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type:
            return None

        # Извлекаем статью
        article = extractor.extract(response.text, norm_url)

        return article

    finally:
        if close_client:
            await client.aclose()
