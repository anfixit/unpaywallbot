"""Тесты шифрования и хранилища аккаунтов."""

import asyncio
import json
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from bot.auth.account_manager import (
    Account,
    AccountManager,
    AccountStorageError,
)
from bot.auth.encryptor import Encryptor, encryptor
from bot.constants import (
    LEGACY_PBKDF2_ITERATIONS,
    LEGACY_PBKDF2_SALT,
)


def test_encryptor_encrypt_decrypt() -> None:
    """Проверка шифрования и дешифрования."""
    test_data = {'test': 'data', 'number': 123}
    encrypted = encryptor.encrypt(test_data)

    envelope = json.loads(encrypted)
    assert envelope['version'] == 2
    assert envelope['salt']
    assert encryptor.decrypt(encrypted) == test_data


def test_encryptor_uses_random_salt() -> None:
    """Одинаковые данные не дают одинаковый envelope."""
    data = {'secret': 'value'}

    first = encryptor.encrypt(data)
    second = encryptor.encrypt(data)

    assert first != second
    assert json.loads(first)['salt'] != json.loads(second)['salt']


def test_encryptor_cookies() -> None:
    """Проверка работы с cookies."""
    cookies = [
        {'name': 'session', 'value': 'abc123'},
    ]
    encrypted = encryptor.encrypt_cookies(cookies)

    assert encryptor.decrypt_cookies(encrypted) == cookies


def test_encryptor_wrong_key() -> None:
    """Неверный ключ не расшифровывает данные."""
    encrypted = encryptor.encrypt({'secret': 'password'})
    other = Encryptor(key=Fernet.generate_key())

    assert other.decrypt(encrypted) is None


def test_encryptor_reads_legacy_token() -> None:
    """Старый Fernet token остаётся доступен для миграции."""
    secret = 'legacy-test-secret-at-least-32-characters'
    codec = Encryptor(secret=secret)
    legacy_key = codec._derive_key(
        secret,
        LEGACY_PBKDF2_SALT,
        LEGACY_PBKDF2_ITERATIONS,
    )
    token = Fernet(legacy_key).encrypt(
        json.dumps({'legacy': True}).encode('utf-8'),
    ).decode('ascii')

    assert codec.decrypt(token) == {'legacy': True}


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Временное хранилище для тестов."""
    return tmp_path / 'sessions' / 'accounts.json'


@pytest.mark.asyncio
async def test_account_manager_add_and_get(
    temp_storage: Path,
) -> None:
    """Добавление и получение личного аккаунта."""
    manager = AccountManager(temp_storage)
    account = Account(
        email='test@example.com',
        password='password123',
        domain='nytimes.com',
        user_id=123,
    )

    await manager.add_account(account, for_user=123)
    result = await manager.get_account_for_url(
        'https://nytimes.com/article',
        user_id=123,
    )

    assert result is not None
    assert result.email == 'test@example.com'
    assert result.domain == 'nytimes.com'


@pytest.mark.asyncio
async def test_account_manager_shared_account(
    temp_storage: Path,
) -> None:
    """Общий аккаунт доступен разным пользователям."""
    manager = AccountManager(temp_storage)
    account = Account(
        email='shared@domain.com',
        password='sharedpass',
        domain='spiegel.de',
        user_id=0,
    )

    await manager.add_account(account)
    first = await manager.get_account_for_url(
        'https://spiegel.de/plus',
        user_id=123,
    )
    second = await manager.get_account_for_url(
        'https://spiegel.de/plus',
        user_id=456,
    )

    assert first is not None
    assert second is not None
    assert first.email == 'shared@domain.com'


@pytest.mark.asyncio
async def test_account_manager_persistence_is_private(
    temp_storage: Path,
) -> None:
    """Файл атомарен, закрыт правами и не содержит пароль."""
    manager = AccountManager(temp_storage)
    account = Account(
        email='persist@test.com',
        password='plain-secret-password',
        domain='ft.com',
        user_id=0,
    )

    await manager.add_account(account)

    assert stat.S_IMODE(temp_storage.stat().st_mode) == 0o600
    assert 'plain-secret-password' not in temp_storage.read_text(
        encoding='utf-8',
    )
    assert not list(temp_storage.parent.glob('.*.tmp'))

    reloaded = AccountManager(temp_storage)
    result = await reloaded.get_account_for_url(
        'https://ft.com/article',
        user_id=1,
    )
    assert result is not None
    assert result.email == 'persist@test.com'


@pytest.mark.asyncio
async def test_account_manager_upserts_duplicate(
    temp_storage: Path,
) -> None:
    """Повторная запись обновляет, а не дублирует аккаунт."""
    manager = AccountManager(temp_storage)
    original = Account(
        email='user@example.com',
        password='old-password',
        domain='example.com',
        user_id=7,
    )
    updated = Account(
        email='user@example.com',
        password='new-password',
        domain='example.com',
        user_id=7,
    )

    await manager.add_account(original, for_user=7)
    await manager.add_account(updated, for_user=7)

    result = await manager.get_account_for_url(
        'https://example.com/article',
        user_id=7,
    )
    assert result is not None
    assert result.password == 'new-password'


@pytest.mark.asyncio
async def test_account_manager_serializes_concurrent_writes(
    temp_storage: Path,
) -> None:
    """Параллельные изменения одного процесса не теряются."""
    manager = AccountManager(temp_storage)
    first = Account(
        email='one@example.com',
        password='secret-one',
        domain='one.example.com',
        user_id=42,
    )
    second = Account(
        email='two@example.com',
        password='secret-two',
        domain='two.example.com',
        user_id=42,
    )

    await asyncio.gather(
        manager.add_account(first, for_user=42),
        manager.add_account(second, for_user=42),
    )

    assert await manager.get_account_for_url(
        'https://one.example.com/article',
        user_id=42,
    ) is not None
    assert await manager.get_account_for_url(
        'https://two.example.com/article',
        user_id=42,
    ) is not None


def test_account_manager_rejects_corrupt_storage(
    temp_storage: Path,
) -> None:
    """Повреждение не превращается в пустое хранилище."""
    temp_storage.parent.mkdir(parents=True)
    temp_storage.write_text(
        'not-an-encrypted-file',
        encoding='utf-8',
    )

    with pytest.raises(
        AccountStorageError,
        match='не расшифровано',
    ):
        AccountManager(temp_storage)
