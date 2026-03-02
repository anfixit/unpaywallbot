"""Утилиты для парсинга, валидации и нормализации URL.

Используются во всех модулях бота для единообразной
обработки URL-адресов статей.
"""

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse

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


def _ensure_scheme(url: str) -> str:
    """Добавить https:// если схема отсутствует."""
    if not url.startswith(('http://', 'https://')):
        return f'https://{url}'
    return url


def extract_domain(url: str) -> str:
    """Извлечь домен без протокола, www и пути.

    Args:
        url: Полный URL (может содержать протокол,
            путь, query).

    Returns:
        Домен вида 'example.com'.
        Пустая строка если URL невалиден.

    Examples:
        >>> extract_domain(
        ...     'https://www.telegraph.co.uk/news/'
        ... )
        'telegraph.co.uk'
        >>> extract_domain('http://nytimes.com/article')
        'nytimes.com'
    """
    if not url or not isinstance(url, str):
        return ''

    try:
        parsed = urlparse(_ensure_scheme(url))
    except ValueError:
        return ''

    domain = parsed.netloc.lower()
    if domain.startswith('www.'):
        domain = domain[4:]

    return domain


def is_valid_url(url: str) -> bool:
    """Проверить, является ли строка валидным URL.

    Args:
        url: Строка для валидации.

    Returns:
        True если URL имеет допустимый формат и схему.

    Examples:
        >>> is_valid_url('https://telegraph.co.uk')
        True
        >>> is_valid_url('not a url')
        False
        >>> is_valid_url('ftp://example.com')
        False
    """
    if not url or not isinstance(url, str):
        return False

    if len(url) > MAX_URL_LENGTH:
        return False

    if '.' not in url and not url.startswith(
        ('http://', 'https://')
    ):
        return False

    try:
        parsed = urlparse(_ensure_scheme(url))
    except ValueError:
        return False

    return bool(
        parsed.scheme in VALID_URL_SCHEMES
        and parsed.netloc
    )


def normalize_url(url: str) -> str:
    """Нормализовать URL к единому формату.

    Принудительно HTTPS, убирает www,
    убирает фрагменты, сохраняет query params.

    Args:
        url: Входной URL.

    Returns:
        Нормализованный URL. Пустая строка
        если вход невалиден.

    Examples:
        >>> normalize_url(
        ...     'http://Telegraph.co.uk/#section'
        ... )
        'https://telegraph.co.uk'
        >>> normalize_url('https://www.nytimes.com/')
        'https://nytimes.com'
    """
    if not url or not is_valid_url(url):
        return ''

    parsed = urlparse(_ensure_scheme(url))

    domain = parsed.netloc.lower()
    if domain.startswith('www.'):
        domain = domain[4:]

    path = parsed.path.rstrip('/') or ''
    query = parsed.query

    normalized = f'https://{domain}{path}'
    if query:
        normalized = f'{normalized}?{query}'

    return normalized


def get_url_hash(url: str) -> str:
    """Создать стабильный SHA-256 хеш для кеширования.

    Нормализует URL перед хешированием, чтобы
    одна и та же статья всегда получала один хеш.

    Args:
        url: URL для хеширования.

    Returns:
        Hex-строка SHA-256 хеша.
        Пустая строка если URL невалиден.
    """
    if not url:
        return ''

    normalized = normalize_url(url)
    if not normalized:
        return ''

    return hashlib.sha256(
        normalized.encode('utf-8')
    ).hexdigest()


def is_same_domain(url1: str, url2: str) -> bool:
    """Проверить, принадлежат ли URL одному домену.

    Полезно для управления сессиями:
    один сайт = одна сессия.

    Args:
        url1: Первый URL.
        url2: Второй URL.

    Returns:
        True если домены совпадают.

    Examples:
        >>> is_same_domain(
        ...     'https://telegraph.co.uk/a',
        ...     'http://telegraph.co.uk/b',
        ... )
        True
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)

    return bool(
        domain1 and domain2 and domain1 == domain2
    )


def extract_path(url: str) -> str:
    """Извлечь path-компонент из URL.

    Args:
        url: Полный URL.

    Returns:
        Путь начинающийся с '/'.
        Пустая строка если URL невалиден.

    Examples:
        >>> extract_path(
        ...     'https://site.com/articles/123'
        ... )
        '/articles/123'
    """
    if not url:
        return ''

    try:
        parsed = urlparse(_ensure_scheme(url))
    except ValueError:
        return ''

    return parsed.path or '/'


def clean_url(url: str) -> str:
    """Очистить URL от трекинговых параметров.

    Удаляет UTM-метки, fbclid, gclid и другие
    трекинговые параметры. Сохраняет остальные
    query params и параметры без значений.

    Args:
        url: URL с возможными трекинговыми параметрами.

    Returns:
        Чистый URL без трекинговых params.

    Examples:
        >>> clean_url(
        ...     'https://site.com/?utm_source=fb&id=123'
        ... )
        'https://site.com/?id=123'
    """
    if not url or not is_valid_url(url):
        return ''

    parsed = urlparse(_ensure_scheme(url))

    if not parsed.query:
        return (
            f'{parsed.scheme}://{parsed.netloc}'
            f'{parsed.path}'
        )

    # parse_qs корректно обрабатывает edge cases
    params = parse_qs(
        parsed.query, keep_blank_values=True,
    )
    clean_params = {
        k: v
        for k, v in params.items()
        if k not in TRACKING_PARAMS
    }

    base = (
        f'{parsed.scheme}://{parsed.netloc}'
        f'{parsed.path}'
    )

    if clean_params:
        query = urlencode(clean_params, doseq=True)
        return f'{base}?{query}'
    return base
