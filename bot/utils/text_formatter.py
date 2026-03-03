"""Утилиты для форматирования текста под Telegram.

Telegram имеет лимит 4096 символов на сообщение.
Этот модуль разбивает длинные тексты на части,
стараясь не резать слова и предложения.
"""

import re
from typing import Final

from bot.constants import MAX_MESSAGE_LENGTH

__all__ = [
    'split_into_chunks',
    'strip_markdown',
    'truncate_with_ellipsis',
]

# Границы для разбиения (в порядке приоритета)
_CHUNK_BOUNDARIES: Final[list[str]] = [
    '\n\n',  # абзацы
    '\n',    # строки
    '. ',    # предложения
    '! ',
    '? ',
    ', ',    # части предложений
    ' ',     # слова
]

# Порог «достаточно близко к концу» для поиска
# пробела при обрезке слова (80% от позиции среза)
_WORD_BREAK_RATIO = 0.8


def split_into_chunks(
    text: str,
    max_length: int = MAX_MESSAGE_LENGTH,
) -> list[str]:
    """Разбить текст на части для Telegram.

    Старается разбивать по границам
    (абзацы → строки → предложения → слова),
    чтобы не обрывать текст на полуслове.

    Args:
        text: Исходный текст.
        max_length: Максимальная длина одной части.

    Returns:
        Список частей текста.
        Пустой список, если текст пустой.

    Examples:
        >>> len(split_into_chunks('A' * 5000))
        2
    """
    if not text:
        return []

    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_at = _find_split_position(
            remaining, max_length,
        )
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()

    return chunks


def _find_split_position(
    text: str,
    max_length: int,
) -> int:
    """Найти позицию для разрыва внутри лимита.

    Перебирает границы в порядке приоритета:
    абзацы → строки → предложения → слова.
    Если ничего не найдено — режет по max_length.

    Args:
        text: Текст, который нужно разбить.
        max_length: Максимальная длина первой части.

    Returns:
        Индекс, по которому можно резать.
    """
    if len(text) <= max_length:
        return len(text)

    search_area = text[:max_length]

    for boundary in _CHUNK_BOUNDARIES:
        pos = search_area.rfind(boundary)
        if pos != -1:
            return pos + len(boundary)

    last_space = search_area.rfind(' ')
    if last_space != -1:
        return last_space + 1

    return max_length


def truncate_with_ellipsis(
    text: str,
    max_length: int = 300,
) -> str:
    """Обрезать текст до указанной длины с '...'.

    Используется для превью и логов.

    Args:
        text: Исходный текст.
        max_length: Максимальная длина (с '...').

    Returns:
        Обрезанный текст с '...' в конце.

    Examples:
        >>> truncate_with_ellipsis('Длинный текст', 10)
        'Длинный...'
    """
    if len(text) <= max_length:
        return text

    cut_at = max_length - 3
    if cut_at <= 0:
        return '...'

    truncated = text[:cut_at]
    last_space = truncated.rfind(' ')

    # Если пробел достаточно близко к концу —
    # режем по слову, а не по символу
    if last_space > cut_at * _WORD_BREAK_RATIO:
        return truncated[:last_space] + '...'

    return truncated + '...'


def strip_markdown(text: str) -> str:
    """Удалить Markdown-разметку из текста.

    Полезно для логов и превью, где разметка не нужна.

    Args:
        text: Текст с возможной Markdown-разметкой.

    Returns:
        Текст без Markdown.

    Examples:
        >>> strip_markdown('**bold** *italic* [link](url)')
        'bold italic link'
    """
    # Ссылки [text](url) → text
    text = re.sub(
        r'\[([^\]]+)\]\([^)]+\)', r'\1', text,
    )
    # **жирный**
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # *курсив*
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # `код`
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # __подчёркнутый__
    text = re.sub(r'__([^_]+)__', r'\1', text)

    return text.strip()
