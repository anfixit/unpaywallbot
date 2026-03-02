"""Тесты для авторизации и аккаунтов."""

from pathlib import Path

import pytest

from bot.auth.account_manager import Account, AccountManager
from bot.auth.encryptor import Encryptor, encryptor


def test_encryptor_encrypt_decrypt():
    """Проверка шифрования и дешифрования."""
    test_data = {'test': 'data', 'number': 123}
    encrypted = encryptor.encrypt(test_data)
    decrypted = encryptor.decrypt(encrypted)

    assert decrypted == test_data


def test_encryptor_cookies():
    """Проверка работы с cookies."""
    cookies = [{'name': 'session', 'value': 'abc123'}]
    encrypted = encryptor.encrypt_cookies(cookies)
    decrypted = encryptor.decrypt_cookies(encrypted)

    assert decrypted == cookies


def test_encryptor_wrong_key():
    """Неверный ключ не расшифровывает данные."""
    data = {'secret': 'password'}
    encrypted = encryptor.encrypt(data)

    # Другой шифровальщик с другим ключом
    other = Encryptor(key=b'wrong-key-32-bytes-length-here!!')
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


def test_account_manager_add_and_get(temp_storage: Path):
    """Добавление и получение аккаунта."""
    manager = AccountManager(temp_storage)

    account = Account(
        email='test@example.com',
        password='password123',
        domain='nytimes.com',
        user_id=123,
    )

    # Добавляем
    import asyncio
    asyncio.run(manager.add_account(account, for_user=123))

    # Получаем
    result = asyncio.run(manager.get_account_for_url(
        'https://nytimes.com/article',
        user_id=123,
    ))

    assert result is not None
    assert result.email == 'test@example.com'
    assert result.domain == 'nytimes.com'


def test_account_manager_shared_account(temp_storage: Path):
    """Общий аккаунт для всех пользователей."""
    manager = AccountManager(temp_storage)

    account = Account(
        email='shared@domain.com',
        password='sharedpass',
        domain='spiegel.de',
        user_id=0,  # общий
    )

    import asyncio
    asyncio.run(manager.add_account(account))

    # Любой пользователь может получить
    result1 = asyncio.run(manager.get_account_for_url(
        'https://spiegel.de/plus',
        user_id=123,
    ))

    result2 = asyncio.run(manager.get_account_for_url(
        'https://spiegel.de/plus',
        user_id=456,
    ))

    assert result1 is not None
    assert result2 is not None
    assert result1.email == 'shared@domain.com'


def test_account_manager_persistence(temp_storage: Path):
    """Проверка сохранения и загрузки."""
    # Первый менеджер — сохраняем
    manager1 = AccountManager(temp_storage)

    account = Account(
        email='test@example.com',
        password='pass',
        domain='nytimes.com',
        user_id=123,
    )

    import asyncio
    asyncio.run(manager1.add_account(account))

    # Второй менеджер — загружаем
    manager2 = AccountManager(temp_storage)

    result = asyncio.run(manager2.get_account_for_url(
        'https://nytimes.com/article',
        user_id=123,
    ))

    assert result is not None
    assert result.email == 'test@example.com'


def test_account_manager_remove(temp_storage: Path):
    """Удаление аккаунта."""
    manager = AccountManager(temp_storage)

    account = Account(
        email='test@example.com',
        password='pass',
        domain='nytimes.com',
        user_id=123,
    )

    import asyncio
    asyncio.run(manager.add_account(account, for_user=123))

    # Проверяем, что есть
    result1 = asyncio.run(manager.get_account_for_url(
        'https://nytimes.com/article',
        user_id=123,
    ))
    assert result1 is not None

    # Удаляем
    removed = asyncio.run(manager.remove_account(
        email='test@example.com',
        domain='nytimes.com',
        user_id=123,
    ))
    assert removed is True

    # Проверяем, что нет
    result2 = asyncio.run(manager.get_account_for_url(
        'https://nytimes.com/article',
        user_id=123,
    ))
    assert result2 is None
