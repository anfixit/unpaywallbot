"""Тесты для точки входа."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.main import (
    set_commands,
    shutdown,
    shutdown_polling,
)


@pytest.mark.asyncio
async def test_set_commands() -> None:
    """Установка команд бота."""
    mock_bot = AsyncMock()
    await set_commands(mock_bot)

    mock_bot.set_my_commands.assert_called_once()
    commands = (
        mock_bot.set_my_commands.call_args[0][0]
    )
    assert len(commands) == 2
    assert commands[0].command == 'start'
    assert commands[1].command == 'help'


@pytest.mark.asyncio
async def test_shutdown() -> None:
    """Завершение работы."""
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()

    with (
        patch(
            'bot.main.get_redis_client',
            return_value=mock_redis,
        ),
        patch('bot.main.shutdown_logging'),
    ):
        await shutdown()
        mock_redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_polling() -> None:
    """Остановка polling при сигнале."""
    mock_task = AsyncMock()
    mock_task.cancel = Mock()

    mock_dp = AsyncMock()
    mock_dp.stop_polling = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.session.close = AsyncMock()

    await shutdown_polling(
        mock_task, mock_dp, mock_bot,
    )

    mock_task.cancel.assert_called_once()
    mock_dp.stop_polling.assert_called_once()
    mock_bot.session.close.assert_called_once()
