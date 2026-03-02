"""Тесты для утилит работы с URL.

Следует паттерну AAA (Arrange-Act-Assert).
Параметризация для граничных условий (раздел 19.7).
"""

import pytest

from bot.utils.url_utils import (
    clean_url,
    extract_domain,
    extract_path,
    get_url_hash,
    is_same_domain,
    is_valid_url,
    normalize_url,
)

# --- extract_domain ---

@pytest.mark.parametrize('url,expected', [
    (
        'https://www.telegraph.co.uk/news/',
        'telegraph.co.uk',
    ),
    ('http://nytimes.com/article', 'nytimes.com'),
    ('https://WWW.FT.COM/content', 'ft.com'),
    ('thetimes.com/article', 'thetimes.com'),
    ('https://sub.domain.co.uk', 'sub.domain.co.uk'),
])
def test_extract_domain_valid(
    url: str,
    expected: str,
) -> None:
    """Извлечение домена из валидных URL."""
    assert extract_domain(url) == expected


@pytest.mark.parametrize('url', [
    '',
    'invalid',
    None,
    123,
    '   ',
])
def test_extract_domain_invalid(url) -> None:
    """Пустая строка для невалидных входов."""
    assert extract_domain(url) == ''


# --- is_valid_url ---

@pytest.mark.parametrize('url', [
    'https://telegraph.co.uk',
    'http://nytimes.com/article?id=1',
    'https://sub.domain.co.uk/path',
    'nytimes.com',
])
def test_is_valid_url_accepts_valid(url: str) -> None:
    """Валидные URL проходят проверку."""
    assert is_valid_url(url) is True


@pytest.mark.parametrize('url', [
    '',
    'not a url',
    'ftp://example.com',
    None,
    'x' * 2049,
    '   ',
    'javascript:alert(1)',
])
def test_is_valid_url_rejects_invalid(url) -> None:
    """Невалидные URL отклоняются."""
    assert is_valid_url(url) is False


# --- normalize_url ---

@pytest.mark.parametrize('url,expected', [
    (
        'http://Telegraph.co.uk/',
        'https://telegraph.co.uk',
    ),
    (
        'https://www.nytimes.com/',
        'https://nytimes.com',
    ),
    (
        'http://site.com/path#fragment',
        'https://site.com/path',
    ),
    (
        'https://site.com/a?key=val',
        'https://site.com/a?key=val',
    ),
])
def test_normalize_url_valid(
    url: str,
    expected: str,
) -> None:
    """Нормализация приводит URL к единому формату."""
    assert normalize_url(url) == expected


def test_normalize_url_empty_on_invalid() -> None:
    """Пустая строка для невалидного входа."""
    assert normalize_url('') == ''
    assert normalize_url('not-a-url') == ''


# --- get_url_hash ---

def test_get_url_hash_stability() -> None:
    """Один URL всегда даёт один хеш."""
    url = 'https://nytimes.com/article'
    hash1 = get_url_hash(url)
    hash2 = get_url_hash(url)

    assert hash1 == hash2
    assert len(hash1) == 64


def test_get_url_hash_normalization() -> None:
    """Варианты одного URL дают одинаковый хеш."""
    hash1 = get_url_hash('http://www.nytimes.com/a/')
    hash2 = get_url_hash('https://nytimes.com/a')

    assert hash1 == hash2


def test_get_url_hash_empty() -> None:
    """Пустой вход — пустой хеш."""
    assert get_url_hash('') == ''
    assert get_url_hash(None) == ''


# --- is_same_domain ---

@pytest.mark.parametrize('url1,url2,expected', [
    (
        'https://telegraph.co.uk/a',
        'http://telegraph.co.uk/b',
        True,
    ),
    (
        'https://nytimes.com',
        'https://www.nytimes.com',
        True,
    ),
    (
        'https://telegraph.co.uk',
        'https://ft.com',
        False,
    ),
    ('', 'https://ft.com', False),
])
def test_is_same_domain(
    url1: str,
    url2: str,
    expected: bool,
) -> None:
    """Сравнение доменов двух URL."""
    assert is_same_domain(url1, url2) is expected


# --- extract_path ---

@pytest.mark.parametrize('url,expected', [
    (
        'https://site.com/articles/123',
        '/articles/123',
    ),
    ('https://site.com', '/'),
    ('https://site.com/', '/'),
])
def test_extract_path(
    url: str,
    expected: str,
) -> None:
    """Извлечение path-компонента."""
    assert extract_path(url) == expected


# --- clean_url ---

def test_clean_url_removes_tracking() -> None:
    """Трекинговые параметры удаляются."""
    # Arrange
    url = (
        'https://site.com/a'
        '?utm_source=fb&id=123&fbclid=abc'
    )

    # Act
    result = clean_url(url)

    # Assert
    assert 'utm_source' not in result
    assert 'fbclid' not in result
    assert 'id=123' in result


def test_clean_url_preserves_non_tracking() -> None:
    """Не-трекинговые параметры сохраняются."""
    url = 'https://site.com/a?page=2&sort=date'

    result = clean_url(url)

    assert 'page=2' in result
    assert 'sort=date' in result


def test_clean_url_no_query() -> None:
    """URL без query params возвращается как есть."""
    url = 'https://site.com/article'

    result = clean_url(url)

    assert result == 'https://site.com/article'


def test_clean_url_all_tracking_removed() -> None:
    """Если все параметры трекинговые — query убирается."""
    url = (
        'https://site.com/a'
        '?utm_source=fb&utm_medium=cpc'
    )

    result = clean_url(url)

    assert '?' not in result
    assert result == 'https://site.com/a'


def test_clean_url_empty_on_invalid() -> None:
    """Невалидный URL — пустая строка."""
    assert clean_url('') == ''
    assert clean_url('not a url') == ''
