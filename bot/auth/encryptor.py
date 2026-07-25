"""Шифрование данных сессий и cookies."""

import base64
import binascii
import json
import secrets
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import (
    PBKDF2HMAC,
)

from bot.config import settings
from bot.constants import (
    LEGACY_PBKDF2_ITERATIONS,
    LEGACY_PBKDF2_SALT,
    PBKDF2_ITERATIONS,
    PBKDF2_SALT_BYTES,
)

__all__ = ['Encryptor', 'encryptor']

_FORMAT_VERSION = 2


class Encryptor:
    """Шифрование и дешифрование данных сессий."""

    def __init__(
        self,
        key: bytes | None = None,
        *,
        secret: str | None = None,
    ) -> None:
        """Инициализировать шифровальщик.

        Args:
            key: Готовый Fernet-ключ для тестов и миграций.
            secret: Парольная фраза. По умолчанию берётся
                из настроек приложения.

        Raises:
            ValueError: Переданы одновременно key и secret.
        """
        if key is not None and secret is not None:
            msg = 'Передайте key или secret, но не оба'
            raise ValueError(msg)

        self._fixed_key = key
        self._secret = secret
        if key is None and secret is None:
            self._secret = (
                settings.encryption_key.get_secret_value()
            )

        if self._fixed_key is not None:
            self._legacy_fernet = Fernet(self._fixed_key)
        else:
            legacy_key = self._derive_key(
                self._require_secret(),
                LEGACY_PBKDF2_SALT,
                LEGACY_PBKDF2_ITERATIONS,
            )
            self._legacy_fernet = Fernet(legacy_key)

    def _require_secret(self) -> str:
        """Вернуть парольную фразу или завершиться явно."""
        if self._secret is None:
            msg = 'Encryptor не содержит secret'
            raise RuntimeError(msg)
        return self._secret

    @staticmethod
    def _derive_key(
        secret: str,
        salt: bytes,
        iterations: int,
    ) -> bytes:
        """Получить Fernet-ключ через PBKDF2-HMAC-SHA256."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        raw_key = kdf.derive(secret.encode('utf-8'))
        return base64.urlsafe_b64encode(raw_key)

    def encrypt(self, data: dict[str, Any]) -> str:
        """Зашифровать словарь в версионированный envelope."""
        json_bytes = json.dumps(
            data,
            ensure_ascii=False,
            separators=(',', ':'),
        ).encode('utf-8')

        if self._fixed_key is not None:
            salt: bytes | None = None
            fernet = Fernet(self._fixed_key)
        else:
            salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
            key = self._derive_key(
                self._require_secret(),
                salt,
                PBKDF2_ITERATIONS,
            )
            fernet = Fernet(key)

        token = fernet.encrypt(json_bytes).decode('ascii')
        envelope = {
            'version': _FORMAT_VERSION,
            'salt': (
                base64.urlsafe_b64encode(salt).decode('ascii')
                if salt is not None
                else None
            ),
            'token': token,
        }
        return json.dumps(
            envelope,
            separators=(',', ':'),
            sort_keys=True,
        )

    def decrypt(
        self,
        encrypted_data: str,
    ) -> dict[str, Any] | None:
        """Расшифровать новый или legacy-формат."""
        try:
            envelope = json.loads(encrypted_data)
        except json.JSONDecodeError:
            return self._decrypt_legacy(encrypted_data)

        if not isinstance(envelope, dict):
            return None
        if envelope.get('version') != _FORMAT_VERSION:
            return None

        token = envelope.get('token')
        if not isinstance(token, str):
            return None

        if self._fixed_key is not None:
            fernet = Fernet(self._fixed_key)
        else:
            salt = self._decode_salt(envelope.get('salt'))
            if salt is None:
                return None
            key = self._derive_key(
                self._require_secret(),
                salt,
                PBKDF2_ITERATIONS,
            )
            fernet = Fernet(key)

        return self._decrypt_token(fernet, token)

    @staticmethod
    def _decode_salt(value: object) -> bytes | None:
        """Проверить и декодировать соль envelope."""
        if not isinstance(value, str):
            return None
        try:
            salt = base64.b64decode(
                value,
                altchars=b'-_',
                validate=True,
            )
        except (binascii.Error, ValueError):
            return None
        if len(salt) != PBKDF2_SALT_BYTES:
            return None
        return salt

    def _decrypt_legacy(
        self,
        encrypted_data: str,
    ) -> dict[str, Any] | None:
        """Расшифровать токен старого формата."""
        return self._decrypt_token(
            self._legacy_fernet,
            encrypted_data,
        )

    @staticmethod
    def _decrypt_token(
        fernet: Fernet,
        token: str,
    ) -> dict[str, Any] | None:
        """Расшифровать Fernet token и проверить JSON."""
        try:
            decrypted = fernet.decrypt(
                token.encode('ascii'),
            )
            payload = json.loads(
                decrypted.decode('utf-8'),
            )
        except (
            InvalidToken,
            UnicodeDecodeError,
            UnicodeEncodeError,
            json.JSONDecodeError,
        ):
            return None

        if not isinstance(payload, dict):
            return None
        return cast(dict[str, Any], payload)

    def encrypt_cookies(
        self,
        cookies: list[dict[str, Any]],
    ) -> str:
        """Зашифровать cookies."""
        return self.encrypt({'cookies': cookies})

    def decrypt_cookies(
        self,
        encrypted: str,
    ) -> list[dict[str, Any]]:
        """Расшифровать cookies."""
        data = self.decrypt(encrypted)
        if not data:
            return []

        raw_cookies = data.get('cookies')
        if not isinstance(raw_cookies, list):
            return []

        return [
            cast(dict[str, Any], cookie)
            for cookie in raw_cookies
            if isinstance(cookie, dict)
        ]


# Синглтон для использования во всём приложении
encryptor = Encryptor()
