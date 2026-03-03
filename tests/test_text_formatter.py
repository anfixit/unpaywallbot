"""Тесты для форматирования текста."""

from bot.utils.text_formatter import (
    split_into_chunks,
    strip_markdown,
    truncate_with_ellipsis,
)


def test_split_into_chunks_short_text() -> None:
    """Короткий текст не разбивается."""
    text = 'Короткий текст'
    chunks = split_into_chunks(
        text, max_length=100,
    )
    assert chunks == [text]


def test_split_into_chunks_long_text() -> None:
    """Длинный текст разбивается на части."""
    text = 'A' * 5000
    chunks = split_into_chunks(
        text, max_length=4096,
    )

    assert len(chunks) == 2
    assert len(chunks[0]) == 4096
    assert len(chunks[1]) == 5000 - 4096


def test_split_into_chunks_respects_boundaries(
) -> None:
    """Разбиение старается не резать предложения."""
    text = (
        'Первое предложение. '
        'Второе предложение. '
        'Третье предложение.'
    )
    # max_length=40 — первые два предложения не
    # влезут, но первое (20 символов) влезет
    chunks = split_into_chunks(
        text, max_length=40,
    )

    # Главное — разбиение произошло по границе
    assert len(chunks) >= 2
    # Первый чанк заканчивается на '. '
    assert chunks[0].rstrip().endswith('.')


def test_truncate_with_ellipsis() -> None:
    """Обрезание с многоточием."""
    text = 'Длинный текст для обрезания'
    truncated = truncate_with_ellipsis(
        text, max_length=20,
    )

    assert truncated.endswith('...')
    assert len(truncated) <= 20
    assert 'обрезания' not in truncated


def test_strip_markdown() -> None:
    """Удаление Markdown-разметки."""
    text = '**bold** *italic* `code` [link](url)'
    clean = strip_markdown(text)

    assert '**' not in clean
    assert '*' not in clean
    assert '`' not in clean
    assert 'link' in clean
    assert 'bold' in clean
    assert 'italic' in clean
