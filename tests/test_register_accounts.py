"""Тесты безопасного CLI регистрации аккаунтов."""

import io
import sys
from unittest.mock import patch

import pytest

from scripts.register_accounts import (
    _normalize_domain,
    _parse_args,
    _read_password,
)


def test_parse_args_does_not_accept_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Пароль отсутствует в process arguments."""
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'register_accounts',
            '--domain',
            'example.com',
            '--email',
            'user@example.com',
            '--user-id',
            '123',
        ],
    )

    args = _parse_args()

    assert not hasattr(args, 'password')
    assert args.password_stdin is False


def test_read_password_uses_hidden_prompt() -> None:
    """Интерактивный пароль читается через getpass."""
    with patch(
        'scripts.register_accounts.getpass.getpass',
        return_value='secret-password',
    ) as get_password:
        password = _read_password(from_stdin=False)

    assert password == 'secret-password'
    get_password.assert_called_once()


def test_read_password_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Automation может передать секрет через stdin."""
    monkeypatch.setattr(
        sys,
        'stdin',
        io.StringIO('secret-password\n'),
    )

    assert _read_password(
        from_stdin=True,
    ) == 'secret-password'


def test_read_password_rejects_empty_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Пустой секрет не сохраняется."""
    monkeypatch.setattr(sys, 'stdin', io.StringIO(''))

    with pytest.raises(ValueError, match='не может быть пустым'):
        _read_password(from_stdin=True)


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('example.com', 'example.com'),
        ('https://www.example.com/path', 'example.com'),
    ],
)
def test_normalize_domain(
    value: str,
    expected: str,
) -> None:
    """CLI сохраняет канонический домен."""
    assert _normalize_domain(value) == expected
