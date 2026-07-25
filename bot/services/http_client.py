"""Безопасный HTTP-клиент для загрузки веб-страниц."""

import httpx

from bot.constants import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_HTTP_RESPONSE_BYTES,
    MAX_REDIRECTS,
)
from bot.security.url_guard import ensure_public_url

__all__ = ['ResponseTooLargeError', 'create_safe_http_client']


class ResponseTooLargeError(httpx.RequestError):
    """Сервер объявил ответ больше допустимого размера."""


async def _validate_request(request: httpx.Request) -> None:
    """Проверить исходный URL и каждый redirect."""
    await ensure_public_url(str(request.url), request=request)


async def _validate_response(response: httpx.Response) -> None:
    """Отклонить заведомо слишком большой ответ."""
    raw_length = response.headers.get('content-length')
    if not raw_length:
        return

    try:
        content_length = int(raw_length)
    except ValueError:
        return

    if content_length <= MAX_HTTP_RESPONSE_BYTES:
        return

    await response.aclose()
    raise ResponseTooLargeError(
        'Ответ превышает допустимый размер',
        request=response.request,
    )


def create_safe_http_client(
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> httpx.AsyncClient:
    """Создать клиент с SSRF-защитой и лимитами."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
        ),
        trust_env=False,
        event_hooks={
            'request': [_validate_request],
            'response': [_validate_response],
        },
    )
