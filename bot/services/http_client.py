"""Безопасная загрузка веб-страниц."""

import httpx

from bot.constants import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_HTTP_RESPONSE_BYTES,
    MAX_REDIRECTS,
)
from bot.security.url_guard import ensure_public_url

__all__ = ['ResponseTooLargeError', 'create_safe_http_client']


class ResponseTooLargeError(httpx.RequestError):
    """Ответ превысил допустимый лимит."""


async def _validate_request(request: httpx.Request) -> None:
    """Проверить исходный URL и каждый redirect."""
    await ensure_public_url(str(request.url), request=request)


async def _buffer_limited_response(
    response: httpx.Response,
) -> None:
    """Прочитать ответ с лимитом decoded-данных."""
    raw_length = response.headers.get('content-length')
    if raw_length:
        try:
            content_length = int(raw_length)
        except ValueError:
            content_length = 0

        if content_length > MAX_HTTP_RESPONSE_BYTES:
            await response.aclose()
            raise ResponseTooLargeError(
                (
                    'Ответ превышает допустимый '
                    'размер'
                ),
                request=response.request,
            )

    chunks: list[bytes] = []
    total_bytes = 0

    async for chunk in response.aiter_bytes():
        total_bytes += len(chunk)
        if total_bytes > MAX_HTTP_RESPONSE_BYTES:
            await response.aclose()
            raise ResponseTooLargeError(
                (
                    'Ответ превышает допустимый '
                    'размер'
                ),
                request=response.request,
            )
        chunks.append(chunk)

    # Hook работает до обычного чтения тела.
    # Сохраняем проверенное тело.
    response._content = b''.join(chunks)  # noqa: SLF001


def create_safe_http_client(
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    connect_timeout_seconds: float | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Создать клиент с SSRF-защитой.

    connect_timeout_seconds отделяет ожидание
    установки соединения от общего таймаута:
    недоступный хост тогда отваливается быстро,
    не расходуя бюджет всего запроса.
    """
    timeout = httpx.Timeout(
        timeout_seconds,
        connect=connect_timeout_seconds or timeout_seconds,
    )
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
        ),
        trust_env=False,
        transport=transport,
        event_hooks={
            'request': [_validate_request],
            'response': [_buffer_limited_response],
        },
    )
