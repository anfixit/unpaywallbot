"""Тесты для middleware."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.types import Chat, Message, User

from bot.middleware.access_log import (
    AccessLogMiddleware,
)
from bot.middleware.rate_limiter import (
    RateLimiterMiddleware,
)
from bot.middleware.whitelist import (
    WhitelistMiddleware,
)


@pytest.fixture
def mock_message():
    """Мок сообщения."""
    message = Mock(spec=Message)
    message.from_user = Mock(spec=User)
    message.from_user.id = 123
    message.from_user.username = 'testuser'
    message.chat = Mock(spec=Chat)
    message.chat.id = 456
    message.text = '/start'
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_handler():
    """Мок хендлера."""
    return AsyncMock(return_value='ok')


@pytest.mark.asyncio
async def test_rate_limiter_allowed(
    mock_message,
    mock_handler,
) -> None:
    """Пользователь не превысил лимиты."""
    middleware = RateLimiterMiddleware()

    mock_redis = AsyncMock()
    mock_redis.client = AsyncMock()
    mock_redis.client.get = AsyncMock(
        return_value='5',
    )
    mock_redis.client.pipeline = Mock()
    mock_pipe = AsyncMock()
    mock_redis.client.pipeline.return_value = (
        mock_pipe
    )

    with patch(
        'bot.middleware.rate_limiter'
        '.get_redis_client',
        return_value=mock_redis,
    ):
        result = await middleware(
            mock_handler, mock_message, {},
        )

    assert result == 'ok'
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limiter_blocked(
    mock_message,
    mock_handler,
) -> None:
    """Пользователь превысил лимит в минуту."""
    middleware = RateLimiterMiddleware(
        rate_per_minute=5,
    )

    mock_redis = AsyncMock()
    mock_redis.client = AsyncMock()
    mock_redis.client.get = AsyncMock(
        return_value='10',
    )

    with patch(
        'bot.middleware.rate_limiter'
        '.get_redis_client',
        return_value=mock_redis,
    ):
        result = await middleware(
            mock_handler, mock_message, {},
        )

    assert result is None
    mock_handler.assert_not_called()
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_whitelist_allowed(
    mock_message,
    mock_handler,
) -> None:
    """Пользователь в белом списке."""
    middleware = WhitelistMiddleware(whitelist=[123])

    result = await middleware(
        mock_handler, mock_message, {},
    )

    assert result == 'ok'
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_whitelist_blocked(
    mock_message,
    mock_handler,
) -> None:
    """Пользователь не в белом списке."""
    middleware = WhitelistMiddleware(whitelist=[456])

    result = await middleware(
        mock_handler, mock_message, {},
    )

    assert result is None
    mock_handler.assert_not_called()
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_access_log(
    mock_message,
    mock_handler,
    tmp_path,
) -> None:
    """Логирование запросов."""
    middleware = AccessLogMiddleware(log_dir=tmp_path)

    result = await middleware(
        mock_handler, mock_message, {},
    )

    assert result == 'ok'
    mock_handler.assert_called_once()

    log_files = list(
        tmp_path.glob('access_*.jsonl'),
    )
    assert len(log_files) == 1

    content = log_files[0].read_text(
        encoding='utf-8',
    )
    log_entry = json.loads(content.strip())
    assert log_entry['user_id'] == 123
    assert log_entry['status'] == 'success'
    assert 'duration_ms' in log_entry
