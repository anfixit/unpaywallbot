"""Значения окружения по умолчанию для локальных тестов.

pytest загружает conftest.py из корня раньше пакетов
тестов, поэтому Settings получает валидную конфигурацию
до импорта ``bot.config``.

Уже заданные переменные не перезаписываются: в CI и при
ручном запуске приоритет остаётся за окружением.
"""

import os

_TEST_ENV: dict[str, str] = {
    'BOT_TOKEN': '123456789:AABBCCDDEEFFaabbccddeeff-1234567890',
    'ENCRYPTION_KEY': 'test-encryption-key-at-least-32-characters',
    'REDIS_URL': 'redis://localhost:6379/0',
    'ALLOWED_USERS': '[]',
    'PUBLIC_ACCESS': 'true',
    'ENV': 'testing',
}

for _name, _value in _TEST_ENV.items():
    os.environ.setdefault(_name, _value)
