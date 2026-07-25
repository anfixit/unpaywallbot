"""Получение HTML-страницы без выполнения JavaScript."""

import logging

import httpx

from bot.constants import BypassMethod
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.services.http_client import create_safe_http_client
from bot.utils.url_utils import extract_domain, normalize_url

__all__ = ['fetch_via_js_disable']

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X'
    ' 10_15_7) AppleWebKit/537.36'
)


async def fetch_via_js_disable(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Загрузить публичный HTML без выполнения JavaScript."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    close_client = client is None
    if client is None:
        client = create_safe_http_client()

    if extractor is None:
        extractor = ContentExtractor()

    try:
        response = await client.get(
            norm_url,
            headers={
                'User-Agent': _DEFAULT_USER_AGENT,
                'Accept': (
                    'text/html,'
                    'application/xhtml+xml'
                ),
            },
        )

        if response.status_code >= 400:
            logger.debug(
                'js_disable: HTTP %d для %s',
                response.status_code,
                extract_domain(norm_url),
            )
            return None

        content_type = response.headers.get(
            'content-type',
            '',
        ).lower()
        if 'text/html' not in content_type:
            return None

        article = extractor.extract(
            response.text,
            norm_url,
        )
        if article and not article.is_empty:
            article.extraction_method = BypassMethod.JS_DISABLE
        return article
    finally:
        if close_client:
            await client.aclose()
