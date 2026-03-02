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
    'truncate_with_ellipsis',
    'strip_markdown',
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


def split_into_chunks(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Разбить текст на части для Telegram.

    Старается разбивать по границам (абзацы → строки → предложения → слова),
    чтобы не обрывать текст на полуслове.

    Args:
        text: Исходный текст.
        max_length: Максимальная длина одной части (обычно 4096).

    Returns:
        Список частей текста. Пустой список, если текст пустой.

    Examples:
        >>> split_into_chunks('A' * 5000)  # 2 части
        ['A' * 4096, 'A' * 904]
    """
    if not text:
        return []

    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Ищем место для разрыва
        split_at = _find_split_position(remaining, max_length)

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()

    return chunks


def _find_split_position(text: str, max_length: int) -> int:
    """Найти позицию для разрыва внутри лимита.

    Перебирает границы в порядке приоритета:
    абзацы → строки → предложения → слова.
    Если ничего не найдено — режет ровно по max_length.

    Args:
        text: Текст, который нужно разбить.
        max_length: Максимальная длина первой части.

    Returns:
        Индекс, по которому можно резать (≤ max_length).
    """
    if len(text) <= max_length:
        return len(text)

    # Ищем границу в пределах max_length
    search_area = text[:max_length]

    for boundary in _CHUNK_BOUNDARIES:
        pos = search_area.rfind(boundary)
        if pos != -1:
            # Возвращаем позицию + длину разделителя
            return pos + len(boundary)

    # Если нет подходящих границ — режем по слову
    last_space = search_area.rfind(' ')
    if last_space != -1:
        return last_space + 1

    # Хуже некуда — режем ровно по лимиту
    return max_length


def truncate_with_ellipsis(text: str, max_length: int = 300) -> str:
    """Обрезать текст до указанной длины, добавив '...'.

    Используется для превью и логов.

    Args:
        text: Исходный текст.
        max_length: Максимальная длина (с учётом '...').

    Returns:
        Обрезанный текст с '...' в конце.

    Examples:
        >>> truncate_with_ellipsis('Длинный текст', 10)
        'Длинный ...'
    """
    if len(text) <= max_length:
        return text

    # Оставляем место для '...'
    cut_at = max_length - 3
    if cut_at <= 0:
        return '...'

    # Стараемся не резать слово
    truncated = text[:cut_at]
    last_space = truncated.rfind(' ')

    if last_space > cut_at * 0.8:  # если нашли пробел достаточно близко к концу
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
    # Удаляем ссылки [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Удаляем **жирный**
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)

    # Удаляем *курсив*
    text = re.sub(r'\*([^*]+)\*', r'\1', text)

    # Удаляем `код`
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Удаляем __подчёркнутый__
    text = re.sub(r'__([^_]+)__', r'\1', text)

    return text.strip()
