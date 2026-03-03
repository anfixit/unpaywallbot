"""Утилиты общего назначения.

Содержит:
- url_utils — работа с URL
- text_formatter — форматирование текста для Telegram
- logger — настройка логирования
"""

from bot.utils.logger import setup_logger, shutdown_logging
from bot.utils.text_formatter import (
    split_into_chunks,
    strip_markdown,
    truncate_with_ellipsis,
)
from bot.utils.url_utils import (
    clean_url,
    extract_domain,
    extract_path,
    get_url_hash,
    is_same_domain,
    is_valid_url,
    normalize_url,
)

__all__ = [
    # URL utils
    'clean_url',
    'extract_domain',
    'extract_path',
    'get_url_hash',
    'is_same_domain',
    'is_valid_url',
    'normalize_url',
    # Text formatter
    'split_into_chunks',
    'strip_markdown',
    'truncate_with_ellipsis',
    # Logger
    'setup_logger',
    'shutdown_logging',
]
