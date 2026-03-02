"""Менеджер аккаунтов пользователей.

Хранит зашифрованные сессии для каждого пользователя
и домена. Позволяет получать аккаунты для разных сайтов.
"""

import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path

from bot.auth.encryptor import encryptor
from bot.utils.url_utils import extract_domain

__all__ = ['Account', 'AccountManager']


@dataclass
class Account:
    """Аккаунт для доступа к сайту.

    Поле password хранится зашифрованным на диске
    через Encryptor. В памяти — только на время
    использования в headless-браузере.
    """

    email: str
    password: str
    domain: str
    user_id: int
    session_cookies: list[dict] | None = None
    last_used: str | None = None
    is_active: bool = True


class AccountManager:
    """Менеджер аккаунтов с зашифрованным хранением."""

    def __init__(self, storage_path: Path) -> None:
        """Инициализировать менеджер аккаунтов.

        Args:
            storage_path: Путь к файлу с данными.
        """
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(
            parents=True, exist_ok=True,
        )
        # domain -> list of accounts
        self._accounts: dict[str, list[Account]] = {}
        # user_id -> accounts
        self._user_accounts: dict[
            int, list[Account]
        ] = {}
        self._load_sync()

    def _load_sync(self) -> None:
        """Загрузить данные из файла (синхронно).

        Вызывается только в __init__. Для runtime
        используй async-версию _load().
        """
        if not self.storage_path.exists():
            return

        try:
            encrypted = self.storage_path.read_text(
                encoding='utf-8',
            )
            self._parse_data(encrypted)
        except Exception:
            self._accounts = {}
            self._user_accounts = {}

    def _parse_data(self, encrypted: str) -> None:
        """Расшифровать и распарсить данные."""
        data = encryptor.decrypt(encrypted)
        if not data:
            return

        for domain, accs in data.get(
            'by_domain', {},
        ).items():
            self._accounts[domain] = [
                Account(**a) for a in accs
            ]

        for uid_str, accs in data.get(
            'by_user', {},
        ).items():
            self._user_accounts[int(uid_str)] = [
                Account(**a) for a in accs
            ]

    async def _save(self) -> None:
        """Зашифровать и сохранить в файл.

        Использует to_thread чтобы не блокировать
        event loop (§17.1).
        """
        by_domain = {
            domain: [asdict(a) for a in accs]
            for domain, accs in self._accounts.items()
        }
        by_user = {
            str(uid): [asdict(a) for a in accs]
            for uid, accs
            in self._user_accounts.items()
        }

        data = {
            'by_domain': by_domain,
            'by_user': by_user,
        }

        encrypted = encryptor.encrypt(data)
        await asyncio.to_thread(
            self.storage_path.write_text,
            encrypted,
            'utf-8',
        )

    async def get_account_for_url(
        self,
        url: str,
        user_id: int,
    ) -> Account | None:
        """Получить аккаунт для URL и пользователя.

        Сначала ищет личный аккаунт, затем общий.

        Args:
            url: URL статьи.
            user_id: ID пользователя Telegram.

        Returns:
            Аккаунт или None.
        """
        domain = extract_domain(url)

        # Личный аккаунт пользователя
        user_accs = self._user_accounts.get(
            user_id, [],
        )
        for acc in user_accs:
            if acc.domain == domain and acc.is_active:
                return acc

        # Общий аккаунт для домена
        domain_accs = self._accounts.get(domain, [])
        for acc in domain_accs:
            if acc.is_active:
                return acc

        return None

    async def add_account(
        self,
        account: Account,
        for_user: int | None = None,
    ) -> None:
        """Добавить аккаунт.

        Args:
            account: Аккаунт.
            for_user: Привязать к пользователю.
        """
        if for_user:
            account.user_id = for_user
            if for_user not in self._user_accounts:
                self._user_accounts[for_user] = []
            self._user_accounts[for_user].append(
                account,
            )
        else:
            account.user_id = 0
            domain = account.domain
            if domain not in self._accounts:
                self._accounts[domain] = []
            self._accounts[domain].append(account)

        await self._save()

    async def save_account(
        self,
        account: Account,
    ) -> None:
        """Сохранить изменения в аккаунте.

        Например, обновить cookies после логина.
        """
        target = (
            self._user_accounts.get(
                account.user_id, [],
            )
            if account.user_id
            else self._accounts.get(
                account.domain, [],
            )
        )

        for i, acc in enumerate(target):
            if (
                acc.email == account.email
                and acc.domain == account.domain
            ):
                target[i] = account
                break

        await self._save()

    async def remove_account(
        self,
        email: str,
        domain: str,
        user_id: int | None = None,
    ) -> bool:
        """Удалить аккаунт.

        Args:
            email: Email аккаунта.
            domain: Домен.
            user_id: Если указан, удаляем личный.

        Returns:
            True если удалили, False если не нашли.
        """
        if user_id:
            accs = self._user_accounts.get(
                user_id, [],
            )
            filtered = [
                a for a in accs
                if not (
                    a.email == email
                    and a.domain == domain
                )
            ]
            if len(filtered) != len(accs):
                self._user_accounts[user_id] = filtered
                await self._save()
                return True
        else:
            accs = self._accounts.get(domain, [])
            filtered = [
                a for a in accs
                if a.email != email
            ]
            if len(filtered) != len(accs):
                self._accounts[domain] = filtered
                await self._save()
                return True

        return False
