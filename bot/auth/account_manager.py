"""Менеджер зашифрованных аккаунтов пользователей."""

import asyncio
import os
import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from bot.auth.encryptor import encryptor
from bot.utils.url_utils import extract_domain

__all__ = [
    'Account',
    'AccountManager',
    'AccountStorageError',
]

_FILE_FORMAT_VERSION = 1


class AccountStorageError(RuntimeError):
    """Хранилище аккаунтов нельзя безопасно использовать."""


@dataclass
class Account:
    """Аккаунт для доступа к сайту.

    Поле password хранится зашифрованным на диске
    через Encryptor. В памяти оно существует только
    во время работы процесса.
    """

    email: str
    password: str
    domain: str
    user_id: int
    session_cookies: list[dict[str, object]] | None = None
    last_used: str | None = None
    is_active: bool = True


class AccountManager:
    """Менеджер аккаунтов с атомарным хранением."""

    def __init__(self, storage_path: Path) -> None:
        """Инициализировать менеджер аккаунтов.

        Args:
            storage_path: Путь к зашифрованному файлу.

        Raises:
            AccountStorageError: Существующий файл нельзя
                прочитать, расшифровать или проверить.
        """
        self.storage_path = storage_path
        parent_exists = self.storage_path.parent.exists()
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )
        if not parent_exists:
            self.storage_path.parent.chmod(0o700)

        self._accounts: dict[str, list[Account]] = {}
        self._user_accounts: dict[int, list[Account]] = {}
        self._lock = asyncio.Lock()
        self._load_sync()

    def _load_sync(self) -> None:
        """Загрузить и проверить существующее хранилище."""
        if not self.storage_path.exists():
            return

        try:
            encrypted = self.storage_path.read_text(
                encoding='utf-8',
            )
            data = encryptor.decrypt(encrypted)
            if data is None:
                msg = (
                    'Хранилище не расшифровано. '
                    'Проверьте ENCRYPTION_KEY.'
                )
                raise AccountStorageError(msg)
            self._parse_data(data)
            self.storage_path.chmod(0o600)
        except AccountStorageError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            msg = 'Повреждено хранилище аккаунтов'
            raise AccountStorageError(msg) from exc

    def _parse_data(
        self,
        data: Mapping[str, Any],
    ) -> None:
        """Проверить расшифрованный формат файла."""
        version = data.get('version', 0)
        if version not in {0, _FILE_FORMAT_VERSION}:
            msg = f'Неизвестная версия хранилища: {version}'
            raise AccountStorageError(msg)

        by_domain = data.get('by_domain', {})
        by_user = data.get('by_user', {})
        if not isinstance(by_domain, dict):
            msg = 'Поле by_domain должно быть объектом'
            raise AccountStorageError(msg)
        if not isinstance(by_user, dict):
            msg = 'Поле by_user должно быть объектом'
            raise AccountStorageError(msg)

        accounts: dict[str, list[Account]] = {}
        user_accounts: dict[int, list[Account]] = {}

        for domain, raw_accounts in by_domain.items():
            if not isinstance(domain, str):
                msg = 'Ключ by_domain должен быть строкой'
                raise AccountStorageError(msg)
            accounts[domain] = self._parse_accounts(
                raw_accounts,
            )

        for raw_user_id, raw_accounts in by_user.items():
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError) as exc:
                msg = 'Ключ by_user должен быть user_id'
                raise AccountStorageError(msg) from exc
            user_accounts[user_id] = self._parse_accounts(
                raw_accounts,
            )

        self._accounts = accounts
        self._user_accounts = user_accounts

    @classmethod
    def _parse_accounts(cls, value: object) -> list[Account]:
        """Проверить список аккаунтов."""
        if not isinstance(value, list):
            msg = 'Список аккаунтов имеет неверный формат'
            raise AccountStorageError(msg)
        return [cls._parse_account(item) for item in value]

    @staticmethod
    def _parse_account(value: object) -> Account:
        """Проверить одну запись аккаунта."""
        if not isinstance(value, dict):
            msg = 'Аккаунт должен быть объектом'
            raise AccountStorageError(msg)

        email = value.get('email')
        password = value.get('password')
        domain = value.get('domain')
        user_id = value.get('user_id')
        cookies = value.get('session_cookies')
        last_used = value.get('last_used')
        is_active = value.get('is_active', True)

        if not isinstance(email, str) or not email:
            msg = 'Некорректный email аккаунта'
            raise AccountStorageError(msg)
        if not isinstance(password, str) or not password:
            msg = 'Некорректный пароль аккаунта'
            raise AccountStorageError(msg)
        if not isinstance(domain, str) or not domain:
            msg = 'Некорректный домен аккаунта'
            raise AccountStorageError(msg)
        if not isinstance(user_id, int):
            msg = 'Некорректный user_id аккаунта'
            raise AccountStorageError(msg)
        if cookies is not None:
            if not isinstance(cookies, list):
                msg = 'Некорректные cookies аккаунта'
                raise AccountStorageError(msg)
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    msg = 'Некорректная запись cookie'
                    raise AccountStorageError(msg)
        if last_used is not None and not isinstance(last_used, str):
            msg = 'Некорректное поле last_used'
            raise AccountStorageError(msg)
        if not isinstance(is_active, bool):
            msg = 'Некорректное поле is_active'
            raise AccountStorageError(msg)

        return Account(
            email=email,
            password=password,
            domain=domain,
            user_id=user_id,
            session_cookies=cookies,
            last_used=last_used,
            is_active=is_active,
        )

    async def _save_unlocked(self) -> None:
        """Зашифровать и атомарно сохранить состояние."""
        data = {
            'version': _FILE_FORMAT_VERSION,
            'by_domain': {
                domain: [asdict(account) for account in accounts]
                for domain, accounts in self._accounts.items()
            },
            'by_user': {
                str(user_id): [
                    asdict(account) for account in accounts
                ]
                for user_id, accounts
                in self._user_accounts.items()
            },
        }
        encrypted = encryptor.encrypt(data)
        await asyncio.to_thread(
            self._atomic_write,
            encrypted,
        )

    def _atomic_write(self, encrypted: str) -> None:
        """Записать файл через fsync и os.replace."""
        temp_path = self.storage_path.with_name(
            f'.{self.storage_path.name}.'
            f'{secrets.token_hex(8)}.tmp',
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temp_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(
                descriptor,
                'w',
                encoding='utf-8',
            ) as file:
                descriptor = None
                file.write(encrypted)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temp_path, self.storage_path)
            self.storage_path.chmod(0o600)
            self._fsync_directory()
        finally:
            if descriptor is not None:
                os.close(descriptor)
            temp_path.unlink(missing_ok=True)

    def _fsync_directory(self) -> None:
        """Зафиксировать замену имени файла на диске."""
        flags = os.O_RDONLY
        if hasattr(os, 'O_DIRECTORY'):
            flags |= os.O_DIRECTORY
        directory = os.open(self.storage_path.parent, flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    async def get_account_for_url(
        self,
        url: str,
        user_id: int,
    ) -> Account | None:
        """Получить личный или общий аккаунт для URL."""
        domain = extract_domain(url)
        async with self._lock:
            for account in self._user_accounts.get(user_id, []):
                if account.domain == domain and account.is_active:
                    return account

            for account in self._accounts.get(domain, []):
                if account.is_active:
                    return account

        return None

    async def add_account(
        self,
        account: Account,
        for_user: int | None = None,
    ) -> None:
        """Добавить или заменить аккаунт."""
        stored_account = replace(
            account,
            user_id=(for_user if for_user is not None else 0),
        )

        async with self._lock:
            if for_user is not None:
                target = self._user_accounts.setdefault(
                    for_user,
                    [],
                )
            else:
                target = self._accounts.setdefault(
                    stored_account.domain,
                    [],
                )

            self._upsert(target, stored_account)
            await self._save_unlocked()

    @staticmethod
    def _upsert(
        target: list[Account],
        account: Account,
    ) -> None:
        """Заменить совпадающий аккаунт или добавить новый."""
        for index, existing in enumerate(target):
            if (
                existing.email == account.email
                and existing.domain == account.domain
            ):
                target[index] = account
                return
        target.append(account)

    async def save_account(
        self,
        account: Account,
    ) -> None:
        """Сохранить обновлённые cookies аккаунта.

        Raises:
            AccountStorageError: Аккаунт не зарегистрирован.
        """
        async with self._lock:
            target = (
                self._user_accounts.get(account.user_id, [])
                if account.user_id
                else self._accounts.get(account.domain, [])
            )

            for index, existing in enumerate(target):
                if (
                    existing.email == account.email
                    and existing.domain == account.domain
                ):
                    target[index] = account
                    await self._save_unlocked()
                    return

        msg = 'Нельзя сохранить незарегистрированный аккаунт'
        raise AccountStorageError(msg)

    async def remove_account(
        self,
        email: str,
        domain: str,
        user_id: int | None = None,
    ) -> bool:
        """Удалить личный или общий аккаунт."""
        async with self._lock:
            if user_id is not None:
                accounts = self._user_accounts.get(user_id, [])
            else:
                accounts = self._accounts.get(domain, [])

            filtered = [
                account
                for account in accounts
                if not (
                    account.email == email
                    and account.domain == domain
                )
            ]
            if len(filtered) == len(accounts):
                return False

            if user_id is not None:
                self._user_accounts[user_id] = filtered
            else:
                self._accounts[domain] = filtered

            await self._save_unlocked()
            return True
