"""Read existing snapshots from public web archives."""

import logging
import re
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from bot.config import settings
from bot.constants import BypassMethod
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.services.http_client import create_safe_http_client
from bot.utils.url_utils import extract_domain, normalize_url

__all__ = [
    'archive_lookup_url',
    'fetch_via_archive',
    'fetch_via_wayback',
    'reset_cooldown',
    'wayback_lookup_url',
]

logger = logging.getLogger(__name__)

_ARCHIVE_BASE = 'https://archive.ph'
_WAYBACK_AVAILABLE_URL = 'https://archive.org/wayback/available'
_WAYBACK_REPLAY_BASE = 'https://web.archive.org/web'
_WAYBACK_REPLAY_HOST = 'web.archive.org'
_WAYBACK_TIMESTAMP_RE = re.compile(r'^\d{14}$')
_WAYBACK_MAX_REDIRECTS = 3

# Архив блокирует часть хостингов целиком. Без
# отдельного лимита на соединение каждая попытка
# съедает десятки секунд из бюджета запроса.
_ARCHIVE_CONNECT_TIMEOUT = 5.0
_ARCHIVE_TOTAL_TIMEOUT = 20.0

# Архив отвечает 429 и страницей с капчей, когда считает
# клиента автоматическим. Повторные запросы в этом
# состоянии бесполезны и лишь добавляют ему нагрузки,
# поэтому после отказа адаптер молчит заданное время.
_RATE_LIMIT_COOLDOWN_SECONDS = 1800.0
_CAPTCHA_MARKERS = ('captcha', 'are you a robot')
_WAYBACK_UNAVAILABLE_MARKERS = (
    'internet archive: temporarily offline',
    'internet archive services are temporarily offline',
)

_blocked_until = 0.0


def _cooldown_remaining() -> float:
    """Сколько секунд ещё не стоит трогать архив."""
    return max(0.0, _blocked_until - time.monotonic())


def _start_cooldown() -> None:
    """Отметить, что архив попросил не беспокоить."""
    global _blocked_until  # noqa: PLW0603
    _blocked_until = time.monotonic() + _RATE_LIMIT_COOLDOWN_SECONDS


def reset_cooldown() -> None:
    """Сбросить паузу (используется в тестах)."""
    global _blocked_until  # noqa: PLW0603
    _blocked_until = 0.0


def _is_challenge(status_code: int, html: str) -> bool:
    """Отличить антибот-заслон от обычной неудачи."""
    if status_code == 429:
        return True
    lowered = html[:4000].lower()
    return any(marker in lowered for marker in _CAPTCHA_MARKERS)
_WAIT_MARKERS = (
    'Saving page',
    'Webpage capture',
    'Waiting',
    'Just a moment',
)


def archive_lookup_url(url: str) -> str | None:
    """Ссылка на снимок для открытия человеком.

    Архив показывает автоматике антибот-проверку, но
    обычному посетителю отдаёт страницу. Поэтому когда
    бот не смог получить текст, он предлагает открыть
    снимок самостоятельно.
    """
    norm_url = normalize_url(url)
    if not norm_url:
        return None
    return f'{_ARCHIVE_BASE}/newest/{norm_url}'


def wayback_lookup_url(url: str) -> str | None:
    """Return a browser link to all Wayback snapshots."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None
    return f'{_WAYBACK_REPLAY_BASE}/*/{norm_url}'


async def fetch_via_archive(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
    wayback_client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Read a snapshot, preferring archive.ph over Wayback.

    The archive.ph adapter remains read-only. If it is blocked,
    challenged or has no usable snapshot, Wayback Machine is tried
    automatically.
    """
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    article = await _fetch_via_archive_ph(
        norm_url,
        extractor=extractor,
        client=client,
    )
    if article and not article.is_empty:
        return article

    logger.debug(
        'archive.ph не дал снимок для %s, пробуем Wayback',
        extract_domain(norm_url),
    )
    return await fetch_via_wayback(
        norm_url,
        extractor=extractor,
        client=wayback_client,
    )


async def _fetch_via_archive_ph(
    norm_url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Read one existing archive.ph snapshot without creating it."""
    remaining = _cooldown_remaining()
    if remaining > 0:
        logger.debug(
            'archive.ph: пауза после отказа, ещё %.0f с',
            remaining,
        )
        return None

    close_client = client is None
    if client is None:
        # Архив закрыт для многих хостингов. Прокси
        # применяется только здесь: адрес назначения
        # фиксирован, поэтому SSRF-проверки не слабеют.
        client = create_safe_http_client(
            timeout_seconds=_ARCHIVE_TOTAL_TIMEOUT,
            connect_timeout_seconds=_ARCHIVE_CONNECT_TIMEOUT,
            proxy=settings.archive_proxy_url or None,
        )

    if extractor is None:
        extractor = ContentExtractor()

    try:
        newest_url = f'{_ARCHIVE_BASE}/newest/{norm_url}'
        try:
            response = await client.get(newest_url)
        except httpx.HTTPError:
            logger.debug(
                'archive.ph недоступен для %s',
                extract_domain(norm_url),
            )
            return None

        if _is_challenge(response.status_code, response.text):
            _start_cooldown()
            logger.warning(
                'archive.ph отклонил запрос (HTTP %d): '
                'антибот-проверка. Пауза на %.0f минут.',
                response.status_code,
                _RATE_LIMIT_COOLDOWN_SECONDS / 60,
            )
            return None

        if response.status_code != 200:
            return None
        if _is_wait_page(response.text):
            return None

        article = extractor.extract(
            response.text,
            norm_url,
        )
        if not article or article.is_empty:
            return None

        article.extraction_method = BypassMethod.ARCHIVE_RELAY
        logger.info(
            'archive.ph: найден снимок для %s (%d символов)',
            extract_domain(norm_url),
            len(article.content),
        )
        return article
    finally:
        if close_client:
            await client.aclose()


async def fetch_via_wayback(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Read the closest available Wayback Machine HTML snapshot."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    close_client = client is None
    if client is None:
        client = create_safe_http_client(
            timeout_seconds=_ARCHIVE_TOTAL_TIMEOUT,
            connect_timeout_seconds=_ARCHIVE_CONNECT_TIMEOUT,
        )

    if extractor is None:
        extractor = ContentExtractor()

    try:
        try:
            response = await client.get(
                _WAYBACK_AVAILABLE_URL,
                params={'url': norm_url},
                follow_redirects=False,
            )
        except httpx.HTTPError:
            logger.debug(
                'Wayback недоступен для %s',
                extract_domain(norm_url),
            )
            return None

        timestamp = _wayback_timestamp(response)
        if timestamp is None:
            return None

        replay_url = (
            f'{_WAYBACK_REPLAY_BASE}/{timestamp}id_/{norm_url}'
        )
        snapshot = await _get_wayback_snapshot(client, replay_url)
        if snapshot is None:
            return None

        lowered = snapshot.text[:4000].lower()
        if any(
            marker in lowered
            for marker in _WAYBACK_UNAVAILABLE_MARKERS
        ):
            return None

        content_type = snapshot.headers.get(
            'content-type', '',
        ).lower()
        if content_type and 'html' not in content_type:
            return None

        article = extractor.extract(snapshot.text, norm_url)
        if not article or article.is_empty:
            return None

        article.extraction_method = BypassMethod.ARCHIVE_RELAY
        logger.info(
            'Wayback: найден снимок для %s (%d символов)',
            extract_domain(norm_url),
            len(article.content),
        )
        return article
    finally:
        if close_client:
            await client.aclose()


def _wayback_timestamp(response: httpx.Response) -> str | None:
    """Extract and validate the closest snapshot timestamp."""
    if response.status_code != 200:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None
    snapshots = payload.get('archived_snapshots')
    if not isinstance(snapshots, dict):
        return None
    closest = snapshots.get('closest')
    if not isinstance(closest, dict):
        return None
    if closest.get('available') is not True:
        return None
    if str(closest.get('status')) != '200':
        return None

    timestamp = closest.get('timestamp')
    if (
        not isinstance(timestamp, str)
        or not _WAYBACK_TIMESTAMP_RE.fullmatch(timestamp)
    ):
        return None
    return timestamp


async def _get_wayback_snapshot(
    client: httpx.AsyncClient,
    replay_url: str,
) -> httpx.Response | None:
    """Follow only redirects that stay inside web.archive.org."""
    current_url = replay_url

    for _ in range(_WAYBACK_MAX_REDIRECTS + 1):
        try:
            response = await client.get(
                current_url,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            return None

        if response.status_code == 200:
            return response
        if response.status_code not in {301, 302, 303, 307, 308}:
            return None

        location = response.headers.get('location')
        if not location:
            return None
        next_url = urljoin(current_url, location)
        parsed = urlsplit(next_url)
        if (
            parsed.scheme not in {'http', 'https'}
            or parsed.hostname != _WAYBACK_REPLAY_HOST
            or parsed.username
            or parsed.password
        ):
            return None
        current_url = urlunsplit(
            ('https', parsed.netloc, parsed.path, parsed.query, '')
        )

    return None


def _is_wait_page(html: str) -> bool:
    """Проверить, является ли страница ожиданием."""
    return any(marker in html for marker in _WAIT_MARKERS)
