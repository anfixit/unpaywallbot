"""Общие фикстуры для тестов.

Обеспечивает:
- Переиспользуемые моки (message, handler, redis)
- Общие фикстуры для Article, AccountManager
- Единообразное создание тестовых данных

Подход: Settings загружается при collection,
field_validator в Settings.parse_allowed_users
обрабатывает пустую строку ALLOWED_USERS=""
корректно (возвращает []).
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.types import Chat, Message, User

from bot.models.article import Article


# --- Telegram mocks ---


@pytest.fixture
def mock_user() -> Mock:
    """Мок пользователя Telegram."""
    user = Mock(spec=User)
    user.id = 123
    user.username = 'testuser'
    user.first_name = 'Test'
    user.last_name = 'User'
    return user


@pytest.fixture
def mock_chat() -> Mock:
    """Мок чата Telegram."""
    chat = Mock(spec=Chat)
    chat.id = 456
    chat.type = 'private'
    return chat


@pytest.fixture
def mock_message(
    mock_user: Mock,
    mock_chat: Mock,
) -> Mock:
    """Мок сообщения Telegram.

    Используется в test_middleware, test_handlers
    и других модулях, работающих с aiogram.
    """
    message = Mock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.text = '/start'
    message.message_id = 1
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    return message


@pytest.fixture
def mock_handler() -> AsyncMock:
    """Мок хендлера для middleware-тестов."""
    return AsyncMock(return_value='ok')


# --- Article fixtures ---


@pytest.fixture
def sample_article() -> Article:
    """Статья с контентом для тестов кеша."""
    return Article(
        url='https://test.com/article',
        content='Test content ' * 100,
        title='Test Article',
        author='Test Author',
    )


@pytest.fixture
def empty_article() -> Article:
    """Пустая статья (is_empty=True)."""
    return Article(url='https://test.com/empty')


# --- Redis mock ---


@pytest.fixture
def mock_redis_client() -> Mock:
    """Мок RedisClient для тестов кеша.

    Возвращает объект с .client (AsyncMock),
    имитирующий подключённый RedisClient.
    """
    redis = Mock()
    redis.client = AsyncMock()
    redis.connect = AsyncMock()
    redis.close = AsyncMock()
    return redis


# --- Temp directories ---


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Временное хранилище для AccountManager."""
    return tmp_path / 'accounts.json'


@pytest.fixture
def temp_log_dir(tmp_path: Path) -> Path:
    """Временная директория для логов."""
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    return log_dir
