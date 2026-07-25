"""Конфигурация приложения из переменных окружения."""

from pathlib import Path
from typing import Literal, Self

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ['settings']


def _find_env_file() -> str | None:
    """Найти первый существующий локальный env-файл."""
    for name in (
        '.env.local',
        '.env.production',
        '.env',
    ):
        if Path(name).exists():
            return name
    return None


class Settings(BaseSettings):
    """Проверенная конфигурация runtime."""

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    bot_token: SecretStr = Field(
        description='Токен Telegram-бота',
    )
    redis_url: str = Field(
        default='redis://localhost:6379/0',
        description='URL Redis',
    )
    encryption_key: SecretStr = Field(
        min_length=32,
        description='Секрет шифрования',
    )

    allowed_users: list[int] = Field(
        default_factory=list,
        description='Разрешённые Telegram user_id',
    )
    public_access: bool = Field(
        default=False,
        description='Разрешить доступ всем пользователям',
    )

    log_level: str = Field(default='INFO')
    env: Literal[
        'development',
        'testing',
        'production',
    ] = Field(default='development')
    request_timeout_seconds: int = Field(
        default=90,
        ge=10,
        le=300,
    )
    log_user_identifiers: bool = Field(
        default=False,
        description='Хранить raw Telegram identifiers в access log',
    )
    telegraph_enabled: bool = Field(
        default=False,
        description=(
            'Разрешить передачу длинных статей в Telegraph'
        ),
    )

    @field_validator('allowed_users', mode='before')
    @classmethod
    def parse_allowed_users(
        cls,
        value: object,
    ) -> object:
        """Обработать пустую строку как пустой список."""
        if isinstance(value, str) and not value.strip():
            return []
        return value

    @field_validator('log_level')
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Нормализовать и проверить уровень логирования."""
        normalized = value.upper()
        allowed = {
            'CRITICAL',
            'ERROR',
            'WARNING',
            'INFO',
            'DEBUG',
        }
        if normalized not in allowed:
            msg = f'Недопустимый LOG_LEVEL: {value}'
            raise ValueError(msg)
        return normalized

    @model_validator(mode='after')
    def validate_production_access(self) -> Self:
        """Не запускать production случайно открытым."""
        if (
            self.env == 'production'
            and not self.public_access
            and not self.allowed_users
        ):
            msg = (
                'Production требует ALLOWED_USERS '
                'или PUBLIC_ACCESS=true'
            )
            raise ValueError(msg)
        return self

    @property
    def is_production(self) -> bool:
        """Признак production-окружения."""
        return self.env == 'production'


# Pydantic Settings supplies required values from the environment.
settings = Settings()  # type: ignore[call-arg]
