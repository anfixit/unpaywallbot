"""Константы приложения.

Все магические числа и строки определены здесь.
Категории значений — через StrEnum (раздел 4.3).
"""

from enum import StrEnum
from typing import Final

__all__ = [
    'ALLOWED_IMAGE_TYPES',
    'BypassMethod',
    'CACHE_TTL_LONG',
    'CACHE_TTL_SHORT',
    'DEFAULT_TIMEOUT_SECONDS',
    'FREEMIUM_MARKERS',
    'MAX_MESSAGE_LENGTH',
    'MAX_RETRY_COUNT',
    'MAX_URL_LENGTH',
    'PBKDF2_ITERATIONS',
    'PBKDF2_SALT',
    'PaywallType',
    'RETRY_BACKOFF_FACTOR',
    'TRACKING_PARAMS',
    'VALID_URL_SCHEMES',
]


# --- Paywall types (StrEnum вместо строк) ---

class PaywallType(StrEnum):
    """Тип paywall целевого издания."""

    SOFT = 'soft'
    METERED = 'metered'
    HARD = 'hard'
    FREEMIUM = 'freemium'
    UNKNOWN = 'unknown'


class BypassMethod(StrEnum):
    """Метод обхода paywall."""

    JS_DISABLE = 'js_disable'
    GOOGLEBOT_SPOOF = 'googlebot_spoof'
    HEADLESS_AUTH = 'headless_auth'
    ARCHIVE_RELAY = 'archive_relay'


# --- Freemium-маркеры в URL/DOM ---
FREEMIUM_MARKERS: Final = frozenset({
    'F+',
    'S+',
    'T+',
    'Z+',
    'plus',
    'reduced=true',
})

# --- URL validation ---
MAX_URL_LENGTH: Final = 2048
VALID_URL_SCHEMES: Final = frozenset({'http', 'https'})

# --- URL cleaning (tracking parameters to remove) ---
TRACKING_PARAMS: Final = frozenset({
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
    '_ga',
})

# --- Шифрование (PBKDF2 + Fernet) ---
PBKDF2_SALT: Final = b'unpaywall_salt_2026'
PBKDF2_ITERATIONS: Final = 100_000

# --- HTTP ---
DEFAULT_TIMEOUT_SECONDS: Final = 30
MAX_RETRY_COUNT: Final = 3
RETRY_BACKOFF_FACTOR: Final = 2

# --- Cache (в секундах) ---
CACHE_TTL_SHORT: Final = 300       # 5 минут
CACHE_TTL_LONG: Final = 86_400     # 24 часа

# --- Telegram ---
MAX_MESSAGE_LENGTH: Final = 4096

# --- Загрузка файлов ---
ALLOWED_IMAGE_TYPES: Final = frozenset({
    'image/jpeg',
    'image/png',
    'image/webp',
})
