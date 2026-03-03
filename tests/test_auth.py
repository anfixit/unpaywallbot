"""Тесты для авторизации и аккаунтов."""

import asyncio
import base64
from pathlib import Path

import pytest

from bot.auth.account_manager import (
    Account,
    AccountManager,
)
from bot.auth.encryptor import Encryptor, encryptor


def test_encryptor_encrypt_decrypt() -> None:
    """Проверка шифрования и дешифрования."""
    test_data = {'test': 'data', 'number': 123}
    encrypted = encryptor.encrypt(test_data)
    decrypted = encryptor.decrypt(encrypted)

    assert decrypted == test_data


def test_encryptor_cookies() -> None:
    """Проверка работы с cookies."""
    cookies = [
        {'name': 'session', 'value': 'abc123'},
    ]
    encrypted = encryptor.encrypt_cookies(cookies)
    decrypted = encryptor.decrypt_cookies(encrypted)

    assert decrypted == cookies


def test_encryptor_wrong_key() -> None:
    """Неверный ключ не расшифровывает данные."""
    data = {'secret': 'password'}
    encrypted = encryptor.encrypt(data)

    # Генерируем валидный, но другой Fernet-ключ
    wrong_key = base64.urlsafe_b64encode(
        b'this-is-a-different-key-32bytes!',
    )
    other = Encryptor(key=wrong_key)
    decrypted = other.decrypt(encrypted)

    assert decrypted is None


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Временное хранилище для тестов."""
    return tmp_path / 'accounts.json'


@pytest.fixture
def manager(temp_storage: Path) -> AccountManager:
    """Менеджер аккаунтов для тестов."""
    return AccountManager(temp_storage)


def test_account_manager_add_and_get(
    temp_storage: Path,
) -> None:
    """Добавление и получение аккаунта."""
    mgr = AccountManager(temp_storage)

    account = Account(
        email='test@example.com',
        password='password123',
        domain='nytimes.com',
        user_id=123,
    )

    asyncio.run(
        mgr.add_account(account, for_user=123),
    )

    result = asyncio.run(
        mgr.get_account_for_url(
            'https://nytimes.com/article',
            user_id=123,
        ),
    )

    assert result is not None
    assert result.email == 'test@example.com'
    assert result.domain == 'nytimes.com'


def test_account_manager_shared_account(
    temp_storage: Path,
) -> None:
    """Общий аккаунт для всех пользователей."""
    mgr = AccountManager(temp_storage)

    account = Account(
        email='shared@domain.com',
        password='sharedpass',
        domain='spiegel.de',
        user_id=0,
    )

    asyncio.run(mgr.add_account(account))

    result1 = asyncio.run(
        mgr.get_account_for_url(
            'https://spiegel.de/plus',
            user_id=123,
        ),
    )
    result2 = asyncio.run(
        mgr.get_account_for_url(
            'https://spiegel.de/plus',
            user_id=456,
        ),
    )

    assert result1 is not None
    assert result2 is not None
    assert result1.email == 'shared@domain.com'


def test_account_manager_persistence(
    temp_storage: Path,
) -> None:
    """Проверка сохранения и загрузки."""
    mgr = AccountManager(temp_storage)

    account = Account(
        email='persist@test.com',
        password='pass',
        domain='ft.com',
        user_id=0,
    )

    asyncio.run(mgr.add_account(account))

    # Новый менеджер читает с диска
    mgr2 = AccountManager(temp_storage)
    result = asyncio.run(
        mgr2.get_account_for_url(
            'https://ft.com/article', user_id=1,
        ),
    )

    assert result is not None
    assert result.email == 'persist@test.com'
