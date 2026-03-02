"""Тесты для точки входа."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.main import set_commands, shutdown, shutdown_polling


@pytest.mark.asyncio
async def test_set_commands():
    """Установка команд бота."""
    mock_bot = AsyncMock()
    await set_commands(mock_bot)

    mock_bot.set_my_commands.assert_called_once()
    commands = mock_bot.set_my_commands.call_args[0][0]
    assert len(commands) == 2
    assert commands[0].command == 'start'
    assert commands[1].command == 'help'


@pytest.mark.asyncio
async def test_shutdown():
    """Завершение работы."""
    with patch('bot.main.redis_client') as mock_redis:
        mock_redis.close = AsyncMock()

        await shutdown()

        mock_redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_polling():
    """Остановка polling при сигнале."""
    mock_task = AsyncMock()
    mock_task.cancel = Mock()

    mock_dp = AsyncMock()
    mock_dp.stop_polling = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.session.close = AsyncMock()

    await shutdown_polling(mock_task, mock_dp, mock_bot)

    mock_task.cancel.assert_called_once()
    mock_dp.stop_polling.assert_called_once()
    mock_bot.session.close.assert_called_once()
