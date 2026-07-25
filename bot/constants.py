"""Константы приложения."""

from enum import StrEnum
from typing import Final

__all__ = [
    'ALLOWED_IMAGE_TYPES',
    'BypassMethod',
    'CACHE_TTL_LONG',
    'CACHE_TTL_SHORT',
    'DEFAULT_TIMEOUT_SECONDS',
    'FREEMIUM_MARKERS',
    'LEGACY_PBKDF2_ITERATIONS',
    'LEGACY_PBKDF2_SALT',
    'MAX_HTTP_RESPONSE_BYTES',
    'MAX_MESSAGE_LENGTH',
    'MAX_REDIRECTS',
    'MAX_RETRY_COUNT',
    'MAX_URL_LENGTH',
    'PBKDF2_ITERATIONS',
    'PBKDF2_SALT_BYTES',
    'PaywallType',
    'RETRY_BACKOFF_FACTOR',
    'TRACKING_PARAMS',
    'VALID_URL_SCHEMES',
]


class PaywallType(StrEnum):
    """Тип paywall целевого издания."""

    SOFT = 'soft'
    METERED = 'metered'
    HARD = 'hard'
    FREEMIUM = 'freemium'
    UNKNOWN = 'unknown'


class BypassMethod(StrEnum):
    """Метод получения содержимого страницы."""

    JS_DISABLE = 'js_disable'
    GOOGLEBOT_SPOOF = 'googlebot_spoof'
    HEADLESS_AUTH = 'headless_auth'
    ARCHIVE_RELAY = 'archive_relay'
    WSJ_BYPASS = 'wsj_bypass'


FREEMIUM_MARKERS: Final = frozenset({
    'F+',
    'S+',
    'T+',
    'Z+',
    'plus',
    'reduced=true',
})

MAX_URL_LENGTH: Final = 2048
VALID_URL_SCHEMES: Final = frozenset({'http', 'https'})

TRACKING_PARAMS: Final = frozenset({
    '_ga',
    'fbclid',
    'gclid',
    'mc_cid',
    'mc_eid',
    'utm_campaign',
    'utm_content',
    'utm_medium',
    'utm_source',
    'utm_term',
    'yclid',
})

PBKDF2_SALT_BYTES: Final = 16
PBKDF2_ITERATIONS: Final = 600_000
LEGACY_PBKDF2_SALT: Final = b'unpaywall_salt_2026'
LEGACY_PBKDF2_ITERATIONS: Final = 100_000

DEFAULT_TIMEOUT_SECONDS: Final = 30
MAX_RETRY_COUNT: Final = 3
RETRY_BACKOFF_FACTOR: Final = 2
MAX_REDIRECTS: Final = 5
MAX_HTTP_RESPONSE_BYTES: Final = 5 * 1024 * 1024

CACHE_TTL_SHORT: Final = 300
CACHE_TTL_LONG: Final = 86_400

MAX_MESSAGE_LENGTH: Final = 4096

ALLOWED_IMAGE_TYPES: Final = frozenset({
    'image/jpeg',
    'image/png',
    'image/webp',
})
