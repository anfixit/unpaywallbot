"""Конфигурация приложения из env-переменных.

Использует pydantic-settings (раздел 3.3 стандарта).
SecretStr не попадает в логи при print().

Приоритет загрузки:
  .env.local → .env.production → .env
"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

__all__ = ['settings']


def _find_env_file() -> str | None:
    """Найти первый существующий .env файл."""
    for name in ('.env.local', '.env.production', '.env'):
        if Path(name).exists():
            return name
    return None


class Settings(BaseSettings):
    """Конфигурация приложения.

    Обязательные поля (без default) вызовут
    ValidationError при отсутствии в env.
    """

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    # Telegram
    bot_token: SecretStr = Field(
        description='Токен Telegram-бота от BotFather',
    )

    # Redis
    redis_url: str = Field(
        default='redis://localhost:6379/0',
        description='URL подключения к Redis',
    )

    # Безопасность
    encryption_key: SecretStr = Field(
        min_length=16,
        description='Ключ шифрования сессий',
    )
    allowed_users: list[int] = Field(
        default=[],
        description=(
            'Whitelist Telegram user_id. '
            'Пустой список = доступ всем.'
        ),
    )

    # Логирование
    log_level: str = Field(default='INFO')

    # Окружение
    env: str = Field(default='development')

    @property
    def is_production(self) -> bool:
        """Продакшн-окружение."""
        return self.env == 'production'


# Синглтон — создаётся один раз при импорте.
# Если обязательные поля не заданы, Pydantic
# выбросит ValidationError с понятным traceback.
settings = Settings()
