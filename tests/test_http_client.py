"""Тесты безопасного HTTP-клиента."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bot.services.http_client import (
    ResponseTooLargeError,
    create_safe_http_client,
)


class ChunkedStream(httpx.AsyncByteStream):
    """Тестовый поток ответа."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_chunked_response_is_limited() -> None:
    """Ограничить ответ без Content-Length."""
    stream = ChunkedStream([b'abcd', b'efgh'])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            stream=stream,
        )

    with (
        patch(
            'bot.services.http_client.ensure_public_url',
            new=AsyncMock(),
        ),
        patch(
            'bot.services.http_client.MAX_HTTP_RESPONSE_BYTES',
            6,
        ),
    ):
        async with create_safe_http_client(
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(ResponseTooLargeError):
                await client.get('https://example.com/article')

    assert stream.closed is True


@pytest.mark.asyncio
async def test_limited_response_remains_readable() -> None:
    """Сохранить проверенное тело ответа."""
    stream = ChunkedStream([b'hello', b' world'])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            stream=stream,
        )

    with patch(
        'bot.services.http_client.ensure_public_url',
        new=AsyncMock(),
    ):
        async with create_safe_http_client(
            transport=httpx.MockTransport(handler),
        ) as client:
            response = await client.get(
                'https://example.com/article',
            )

    assert response.text == 'hello world'
