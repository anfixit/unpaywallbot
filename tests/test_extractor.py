"""Тесты для извлечения контента."""

import pytest

from bot.services.content_extractor import ContentExtractor


@pytest.fixture
def extractor() -> ContentExtractor:
    """Экстрактор для тестов."""
    return ContentExtractor(min_text_length=10)


def test_extract_simple_html(extractor: ContentExtractor) -> None:
    """Извлечение из простого HTML."""
    html = '''
    <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test Article</h1>
                <p>This is the article content.</p>
                <p>It has multiple paragraphs.</p>
            </article>
        </body>
    </html>
    '''
    article = extractor.extract(html, 'https://test.com/article')

    assert article is not None
    assert article.title == 'Test Article'
    assert 'article content' in article.content
    assert 'multiple paragraphs' in article.content


def test_extract_empty_html(extractor: ContentExtractor) -> None:
    """Пустой HTML возвращает None."""
    assert extractor.extract('', 'https://test.com') is None
    assert extractor.extract('   ', 'https://test.com') is None


def test_extract_too_short(extractor: ContentExtractor) -> None:
    """Слишком короткий текст не считается статьёй."""
    html = '<html><body><p>Hi</p></body></html>'
    article = extractor.extract(html, 'https://test.com')

    assert article is None


def test_html_to_text_strip_tags(extractor: ContentExtractor) -> None:
    """Проверка преобразования HTML в текст."""
    html = '<p>Hello <b>world</b>!</p>'
    text = extractor._html_to_text(html)

    assert text == 'Hello world!'


def test_author_extraction(extractor: ContentExtractor) -> None:
    """Извлечение автора из meta-тегов."""
    html = '''
    <html>
        <head>
            <meta name="author" content="John Doe">
        </head>
        <body>Content</body>
    </html>
    '''
    author = extractor._extract_author(html)

    assert author == 'John Doe'
