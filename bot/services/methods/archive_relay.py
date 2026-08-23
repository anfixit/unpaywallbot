"""Read an existing public snapshot from archive.ph."""

import logging
import time

import httpx

from bot.config import settings
from bot.constants import BypassMethod
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.services.http_client import create_safe_http_client
from bot.utils.url_utils import extract_domain, normalize_url

__all__ = ['fetch_via_archive', 'reset_cooldown']

logger = logging.getLogger(__name__)

_ARCHIVE_BASE = 'https://archive.ph'

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


async def fetch_via_archive(
    url: str,
    extractor: ContentExtractor | None = None,
    client: httpx.AsyncClient | None = None,
) -> Article | None:
    """Получить только уже существующий публичный снимок."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None

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


def _is_wait_page(html: str) -> bool:
    """Проверить, является ли страница ожиданием."""
    return any(marker in html for marker in _WAIT_MARKERS)
