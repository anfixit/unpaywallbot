"""Шифрование данных сессий и cookies.

Использует Fernet (симметричное шифрование) на основе
ключа из settings. Все чувствительные данные хранятся
только в зашифрованном виде.
"""

import base64
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import (
    PBKDF2HMAC,
)

from bot.config import settings
from bot.constants import PBKDF2_ITERATIONS, PBKDF2_SALT

__all__ = ['Encryptor', 'encryptor']


class Encryptor:
    """Шифрование и дешифрование данных сессий.

    Пример::

        enc = Encryptor()
        encrypted = enc.encrypt({'cookies': [...]})
        decrypted = enc.decrypt(encrypted)
    """

    def __init__(
        self,
        key: bytes | None = None,
    ) -> None:
        """Инициализировать шифровальщик.

        Args:
            key: Ключ Fernet (если None, деривируется
                из settings.encryption_key).
        """
        if key is None:
            secret = (
                settings.encryption_key.get_secret_value()
            )
            key = self._derive_key(secret)

        self.fernet = Fernet(key)

    @staticmethod
    def _derive_key(secret: str) -> bytes:
        """Получить ключ для Fernet из секрета.

        Fernet требует 32 байта в base64-urlsafe.
        Используем PBKDF2HMAC для деривации из
        парольной фразы.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=PBKDF2_SALT,
            iterations=PBKDF2_ITERATIONS,
        )
        raw_key = kdf.derive(secret.encode('utf-8'))
        return base64.urlsafe_b64encode(raw_key)

    def encrypt(self, data: dict[str, Any]) -> str:
        """Зашифровать данные.

        Args:
            data: Словарь (cookies, логины, пароли).

        Returns:
            Зашифрованная строка в base64.
        """
        json_bytes = json.dumps(
            data, ensure_ascii=False,
        ).encode('utf-8')
        encrypted = self.fernet.encrypt(json_bytes)
        return encrypted.decode('utf-8')

    def decrypt(
        self,
        encrypted_data: str,
    ) -> dict[str, Any] | None:
        """Расшифровать данные.

        Args:
            encrypted_data: Зашифрованная строка.

        Returns:
            Исходные данные или None при ошибке
            (неверный ключ, повреждённые данные).
        """
        try:
            decrypted = self.fernet.decrypt(
                encrypted_data.encode('utf-8'),
            )
            return json.loads(
                decrypted.decode('utf-8'),
            )
        except InvalidToken:
            return None
        except json.JSONDecodeError:
            return None

    def encrypt_cookies(
        self,
        cookies: list[dict],
    ) -> str:
        """Зашифровать cookies.

        Args:
            cookies: Список cookies от браузера.

        Returns:
            Зашифрованная строка.
        """
        return self.encrypt({'cookies': cookies})

    def decrypt_cookies(
        self,
        encrypted: str,
    ) -> list[dict]:
        """Расшифровать cookies.

        Args:
            encrypted: Зашифрованная строка.

        Returns:
            Список cookies или пустой список.
        """
        data = self.decrypt(encrypted)
        if data and 'cookies' in data:
            return data['cookies']
        return []


# Синглтон для использования во всём приложении
encryptor = Encryptor()
