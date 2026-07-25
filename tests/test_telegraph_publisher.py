"""Тесты безопасной публикации в Telegraph."""

from bot.models.telegraph_publisher import _text_to_html


def test_text_to_html_escapes_article_markup() -> None:
    """Не интерпретировать HTML статьи."""
    result = _text_to_html(
        '<script>alert(1)</script>\nnext',
    )

    assert '<script>' not in result
    assert '&lt;script&gt;' in result
    assert '<br>' in result


def test_text_to_html_escapes_source_url() -> None:
    """Не позволять сломать href атрибут."""
    result = _text_to_html(
        'Article',
        'https://example.com/" onclick="alert(1)',
    )

    assert '" onclick="' not in result
    assert '&quot; onclick=&quot;' in result
