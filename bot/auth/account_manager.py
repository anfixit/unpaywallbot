"""Менеджер аккаунтов пользователей.

Хранит зашифрованные сессии для каждого пользователя и домена.
Позволяет получать аккаунты для разных сайтов.
"""

from dataclasses import asdict, dataclass
from pathlib import Path

from bot.auth.encryptor import encryptor
from bot.utils.url_utils import extract_domain

__all__ = ['Account', 'AccountManager']


@dataclass
class Account:
    """Аккаунт для доступа к сайту."""

    email: str
    password: str
    domain: str
    user_id: int
    session_cookies: list | None = None
    last_used: str | None = None
    is_active: bool = True


class AccountManager:
    """Менеджер аккаунтов с хранением в зашифрованном виде."""

    def __init__(self, storage_path: Path) -> None:
        """Инициализировать менеджер аккаунтов.

        Args:
            storage_path: Путь к файлу с зашифрованными данными.
        """
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._accounts: dict[str, list[Account]] = {}  # domain -> list of accounts
        self._user_accounts: dict[int, list[Account]] = {}  # user_id -> accounts
        self._load()

    def _load(self) -> None:
        """Загрузить и расшифровать данные из файла."""
        if not self.storage_path.exists():
            return

        try:
            encrypted = self.storage_path.read_text(encoding='utf-8')
            data = encryptor.decrypt(encrypted)

            if not data:
                return

            # Восстанавливаем аккаунты
            for domain, accounts_data in data.get('by_domain', {}).items():
                self._accounts[domain] = [
                    Account(**acc) for acc in accounts_data
                ]

            for user_id_str, accounts_data in data.get('by_user', {}).items():
                self._user_accounts[int(user_id_str)] = [
                    Account(**acc) for acc in accounts_data
                ]

        except Exception:
            # При ошибке начинаем с пустым хранилищем
            self._accounts = {}
            self._user_accounts = {}

    def _save(self) -> None:
        """Зашифровать и сохранить данные в файл."""
        # Подготавливаем данные для сериализации
        by_domain = {}
        for domain, accounts in self._accounts.items():
            by_domain[domain] = [asdict(acc) for acc in accounts]

        by_user = {}
        for user_id, accounts in self._user_accounts.items():
            by_user[str(user_id)] = [asdict(acc) for acc in accounts]

        data = {
            'by_domain': by_domain,
            'by_user': by_user,
        }

        encrypted = encryptor.encrypt(data)
        self.storage_path.write_text(encrypted, encoding='utf-8')

    async def get_account_for_url(
        self,
        url: str,
        user_id: int,
    ) -> Account | None:
        """Получить аккаунт для URL и пользователя.

        Args:
            url: URL статьи.
            user_id: ID пользователя Telegram.

        Returns:
            Аккаунт или None.
        """
        domain = extract_domain(url)

        # Ищем аккаунт пользователя для этого домена
        user_accounts = self._user_accounts.get(user_id, [])
        for account in user_accounts:
            if account.domain == domain and account.is_active:
                return account

        # Если нет — ищем общий аккаунт для домена
        domain_accounts = self._accounts.get(domain, [])
        if domain_accounts:
            # Берём первый активный
            for account in domain_accounts:
                if account.is_active:
                    return account

        return None

    async def add_account(
        self,
        account: Account,
        for_user: int | None = None,
    ) -> None:
        """Добавить аккаунт.

        Args:
            account: Аккаунт.
            for_user: Если указан, аккаунт привязывается к пользователю.
        """
        if for_user:
            # Личный аккаунт пользователя
            account.user_id = for_user
            if for_user not in self._user_accounts:
                self._user_accounts[for_user] = []
            self._user_accounts[for_user].append(account)
        else:
            # Общий аккаунт для домена
            account.user_id = 0
            if account.domain not in self._accounts:
                self._accounts[account.domain] = []
            self._accounts[account.domain].append(account)

        self._save()

    async def save_account(self, account: Account) -> None:
        """Сохранить изменения в аккаунте (например, обновить cookies)."""
        # Обновляем в обоих словарях
        if account.user_id:
            # Личный аккаунт
            accounts = self._user_accounts.get(account.user_id, [])
            for i, acc in enumerate(accounts):
                if acc.email == account.email and acc.domain == account.domain:
                    accounts[i] = account
                    break
        else:
            # Общий аккаунт
            accounts = self._accounts.get(account.domain, [])
            for i, acc in enumerate(accounts):
                if acc.email == account.email:
                    accounts[i] = account
                    break

        self._save()

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
            user_id: Если указан, удаляем личный аккаунт пользователя.

        Returns:
            True если удалили, False если не нашли.
        """
        if user_id:
            accounts = self._user_accounts.get(user_id, [])
            new_accounts = [a for a in accounts if not (a.email == email and a.domain == domain)]
            if len(new_accounts) != len(accounts):
                self._user_accounts[user_id] = new_accounts
                self._save()
                return True
        else:
            accounts = self._accounts.get(domain, [])
            new_accounts = [a for a in accounts if a.email != email]
            if len(new_accounts) != len(accounts):
                self._accounts[domain] = new_accounts
                self._save()
                return True

        return False
