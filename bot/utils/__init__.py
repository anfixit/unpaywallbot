"""Утилиты общего назначения.

Содержит:
- url_utils - работа с URL
- text_formatter - форматирование текста для Telegram
- logger - настройка логирования
"""

from bot.utils.logger import setup_logger
from bot.utils.text_formatter import split_into_chunks, truncate_with_ellipsis
from bot.utils.url_utils import (
    clean_url,
    extract_domain,
    get_url_hash,
    is_same_domain,
    is_valid_url,
    normalize_url,
)

__all__ = [
    # URL utils
    'extract_domain',
    'is_valid_url',
    'normalize_url',
    'get_url_hash',
    'is_same_domain',
    'clean_url',
    # Text formatter
    'split_into_chunks',
    'truncate_with_ellipsis',
    # Logger
    'setup_logger',
]
