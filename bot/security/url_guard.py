"""Проверки URL перед исходящими сетевыми запросами.

Модуль защищает приложение от SSRF: запрещает обращения
к локальным, приватным, служебным и неразрешённым адресам.
Проверка выполняется для исходного URL и каждого редиректа.
"""

import asyncio
import ipaddress
import socket
from typing import NoReturn
from urllib.parse import urlsplit

import httpx

from bot.constants import VALID_URL_SCHEMES

__all__ = ['UnsafeUrlError', 'ensure_public_url']

_ALLOWED_PORTS = frozenset({80, 443})


class UnsafeUrlError(httpx.RequestError):
    """URL не прошёл проверку сетевой безопасности."""


def _raise_unsafe(
    message: str,
    request: httpx.Request | None,
) -> NoReturn:
    raise UnsafeUrlError(message, request=request)


def _validate_url_parts(
    url: str,
    request: httpx.Request | None,
) -> tuple[str, int]:
    """Проверить синтаксис URL и вернуть host/port."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        _raise_unsafe('Некорректный URL', request)

    if parsed.scheme.lower() not in VALID_URL_SCHEMES:
        _raise_unsafe('Разрешены только HTTP и HTTPS', request)

    if parsed.username or parsed.password:
        _raise_unsafe('Credentials в URL запрещены', request)

    hostname = parsed.hostname
    if not hostname:
        _raise_unsafe('URL не содержит hostname', request)

    hostname = hostname.rstrip('.').lower()
    if not hostname or '.' not in hostname:
        _raise_unsafe('Hostname должен быть публичным доменом', request)

    try:
        port = parsed.port
    except ValueError:
        _raise_unsafe('Некорректный порт', request)

    effective_port = port or (
        443 if parsed.scheme.lower() == 'https' else 80
    )
    if effective_port not in _ALLOWED_PORTS:
        _raise_unsafe('Нестандартный порт запрещён', request)

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        _raise_unsafe('IP-адреса в пользовательских URL запрещены', request)

    return hostname, effective_port


async def ensure_public_url(
    url: str,
    *,
    request: httpx.Request | None = None,
) -> None:
    """Убедиться, что URL разрешается только в публичные IP."""
    hostname, port = _validate_url_parts(url, request)
    loop = asyncio.get_running_loop()

    try:
        records = await loop.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError(
            f'Не удалось разрешить домен: {hostname}',
            request=request,
        ) from exc

    if not records:
        _raise_unsafe('DNS не вернул адресов', request)

    addresses = {
        str(record[4][0]).split('%', 1)[0]
        for record in records
    }

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeUrlError(
                f'DNS вернул некорректный адрес: {address}',
                request=request,
            ) from exc

        if not ip.is_global:
            _raise_unsafe(
                f'Доступ к непубличному адресу запрещён: {address}',
                request,
            )
