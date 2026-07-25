"""Парсинг, валидация и нормализация URL."""

import hashlib
import ipaddress
from urllib.parse import (
    ParseResult,
    parse_qs,
    urlencode,
    urlparse,
)

from bot.constants import (
    MAX_URL_LENGTH,
    TRACKING_PARAMS,
    VALID_URL_SCHEMES,
)

__all__ = [
    'clean_url',
    'extract_domain',
    'extract_path',
    'get_url_hash',
    'is_same_domain',
    'is_valid_url',
    'normalize_url',
]

_REJECTED_SCHEMES = frozenset({
    'data',
    'file',
    'ftp',
    'ftps',
    'javascript',
    'mailto',
    'ssh',
    'tel',
})
_ALLOWED_PORTS = frozenset({80, 443})


def _ensure_scheme(url: str) -> str:
    """Добавить HTTPS, если схема не указана."""
    if not url.lower().startswith(('http://', 'https://')):
        return f'https://{url}'
    return url


def _has_rejected_scheme(url: str) -> bool:
    """Проверить явно запрещённую схему."""
    lower = url.lower()
    return any(
        lower.startswith(f'{scheme}:')
        for scheme in _REJECTED_SCHEMES
    )


def _parse_valid_url(
    url: object,
) -> ParseResult | None:
    """Вернуть parsed URL или None после безопасной проверки."""
    if not isinstance(url, str):
        return None

    value = url.strip()
    if not value or len(value) > MAX_URL_LENGTH:
        return None

    if _has_rejected_scheme(value):
        return None

    try:
        parsed = urlparse(_ensure_scheme(value))
    except ValueError:
        return None

    if parsed.scheme.lower() not in VALID_URL_SCHEMES:
        return None

    if parsed.username or parsed.password:
        return None

    hostname = parsed.hostname
    if not hostname:
        return None

    hostname = hostname.rstrip('.').lower()
    if '.' not in hostname or any(char.isspace() for char in hostname):
        return None

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return None

    try:
        port = parsed.port
    except ValueError:
        return None

    if port is not None and port not in _ALLOWED_PORTS:
        return None

    return parsed


def extract_domain(url: object) -> str:
    """Извлечь hostname без ``www``."""
    parsed = _parse_valid_url(url)
    if parsed is None or parsed.hostname is None:
        return ''

    domain = parsed.hostname.rstrip('.').lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def is_valid_url(url: object) -> bool:
    """Проверить безопасный синтаксис публичного HTTP(S) URL."""
    return _parse_valid_url(url) is not None


def normalize_url(url: object) -> str:
    """Нормализовать URL: HTTPS, без www и fragment."""
    parsed = _parse_valid_url(url)
    if parsed is None or parsed.hostname is None:
        return ''

    domain = parsed.hostname.rstrip('.').lower()
    if domain.startswith('www.'):
        domain = domain[4:]

    path = parsed.path.rstrip('/')
    normalized = f'https://{domain}{path}'

    if parsed.query:
        normalized = f'{normalized}?{parsed.query}'

    return normalized


def get_url_hash(url: object) -> str:
    """Создать стабильный SHA-256 хеш нормализованного URL."""
    normalized = normalize_url(url)
    if not normalized:
        return ''

    return hashlib.sha256(
        normalized.encode('utf-8'),
    ).hexdigest()


def is_same_domain(url1: object, url2: object) -> bool:
    """Проверить принадлежность URL одному hostname."""
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    return bool(domain1 and domain1 == domain2)


def extract_path(url: object) -> str:
    """Извлечь path-компонент безопасного URL."""
    parsed = _parse_valid_url(url)
    if parsed is None:
        return ''
    return parsed.path or '/'


def clean_url(url: object) -> str:
    """Удалить известные tracking-параметры."""
    parsed = _parse_valid_url(url)
    if parsed is None:
        return ''

    domain = parsed.hostname or ''
    if domain.startswith('www.'):
        domain = domain[4:]

    base = f'{parsed.scheme.lower()}://{domain}{parsed.path}'
    if not parsed.query:
        return base

    params = parse_qs(
        parsed.query,
        keep_blank_values=True,
    )
    clean_params = {
        key: value
        for key, value in params.items()
        if key not in TRACKING_PARAMS
    }
    if not clean_params:
        return base

    return f'{base}?{urlencode(clean_params, doseq=True)}'
