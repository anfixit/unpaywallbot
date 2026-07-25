"""Тесты защиты исходящих HTTP-запросов."""

import asyncio
import socket
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bot.security.url_guard import (
    UnsafeUrlError,
    ensure_public_url,
)
from bot.utils.url_utils import is_valid_url


@pytest.mark.asyncio
async def test_public_domain_is_allowed() -> None:
    """Публичный DNS-адрес проходит проверку."""
    records = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            '',
            ('93.184.216.34', 443),
        ),
    ]
    loop = asyncio.get_running_loop()

    with patch.object(
        loop,
        'getaddrinfo',
        new=AsyncMock(return_value=records),
    ):
        await ensure_public_url('https://example.com/article')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'address',
    [
        '127.0.0.1',
        '10.0.0.5',
        '169.254.169.254',
        '192.168.1.10',
        '::1',
    ],
)
async def test_private_dns_target_is_rejected(
    address: str,
) -> None:
    """DNS rebinding на приватную сеть блокируется."""
    family = (
        socket.AF_INET6 if ':' in address else socket.AF_INET
    )
    records = [
        (
            family,
            socket.SOCK_STREAM,
            6,
            '',
            (address, 443),
        ),
    ]
    loop = asyncio.get_running_loop()

    with patch.object(
        loop,
        'getaddrinfo',
        new=AsyncMock(return_value=records),
    ):
        with pytest.raises(UnsafeUrlError):
            await ensure_public_url('https://example.com/article')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'url',
    [
        'http://127.0.0.1/admin',
        'http://169.254.169.254/latest/meta-data',
        'https://user:pass@example.com/article',
        'https://example.com:8080/article',
        'file:///etc/passwd',
    ],
)
async def test_unsafe_url_syntax_is_rejected(url: str) -> None:
    """Опасные формы URL отклоняются до DNS."""
    with pytest.raises(UnsafeUrlError):
        await ensure_public_url(url)


@pytest.mark.asyncio
async def test_dns_failure_is_wrapped() -> None:
    """Ошибка DNS возвращается как ошибка HTTP-клиента."""
    loop = asyncio.get_running_loop()

    with patch.object(
        loop,
        'getaddrinfo',
        new=AsyncMock(side_effect=socket.gaierror),
    ):
        with pytest.raises(httpx.RequestError):
            await ensure_public_url('https://missing.example/article')


@pytest.mark.parametrize(
    'url',
    [
        'http://127.0.0.1/admin',
        'http://[::1]/admin',
        'https://user:pass@example.com/article',
        'https://example.com:8080/article',
    ],
)
def test_url_utils_reject_dangerous_targets(url: str) -> None:
    """Синтаксическая проверка отсекает опасные URL."""
    assert is_valid_url(url) is False
