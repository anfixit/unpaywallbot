"""Шифрование данных сессий и cookies.

Использует Fernet (симметричное шифрование) на основе ключа из settings.
Все чувствительные данные хранятся только в зашифрованном виде.
"""

import base64
import json
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

from bot.config import settings

__all__ = ['Encryptor']


class Encryptor:
    """Шифрование и дешифрование данных сессий.

    Пример:
        encryptor = Encryptor()
        encrypted = encryptor.encrypt({'cookies': [...]})
        decrypted = encryptor.decrypt(encrypted)
    """

    def __init__(self, key: bytes | None = None) -> None:
        """Инициализировать шифровальщик.

        Args:
            key: Ключ шифрования (если None, берётся из settings.encryption_key).
        """
        if key is None:
            # Получаем ключ из settings и конвертируем в bytes
            key_str = settings.encryption_key.get_secret_value()
            key = self._derive_key(key_str)

        self.fernet = Fernet(key)

    def _derive_key(self, secret: str) -> bytes:
        """Получить ключ для Fernet из секрета.

        Fernet требует ключ длиной 32 байта в base64-urlsafe формате.
        Используем PBKDF2 для получения ключа из парольной фразы.
        """
        # Соль можно хранить открыто
        salt = b'unpaywall_salt_2026'

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        key = kdf.derive(secret.encode())
        return base64.urlsafe_b64encode(key)

    def encrypt(self, data: dict[str, Any]) -> str:
        """Зашифровать данные.

        Args:
            data: Словарь с данными (cookies, логины, пароли).

        Returns:
            Зашифрованная строка в base64.
        """
        json_str = json.dumps(data, ensure_ascii=False)
        encrypted = self.fernet.encrypt(json_str.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt(self, encrypted_data: str) -> dict[str, Any] | None:
        """Расшифровать данные.

        Args:
            encrypted_data: Зашифрованная строка.

        Returns:
            Исходные данные или None при ошибке.
        """
        try:
            decrypted = self.fernet.decrypt(encrypted_data.encode('utf-8'))
            return json.loads(decrypted.decode('utf-8'))
        except Exception:
            # Не расшифровывается — возможно, ключ сменился
            return None

    def encrypt_cookies(self, cookies: list) -> str:
        """Удобный метод для шифрования cookies.

        Args:
            cookies: Список cookies от браузера.

        Returns:
            Зашифрованная строка.
        """
        return self.encrypt({'cookies': cookies})

    def decrypt_cookies(self, encrypted: str) -> list:
        """Удобный метод для дешифрования cookies.

        Args:
            encrypted: Зашифрованная строка.

        Returns:
            Список cookies или пустой список при ошибке.
        """
        data = self.decrypt(encrypted)
        if data and 'cookies' in data:
            return data['cookies']
        return []


# Синглтон для использования во всём приложении
encryptor = Encryptor()
