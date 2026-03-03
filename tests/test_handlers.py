"""Тесты для Telegram-хендлеров."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.types import Chat, Message, User

from bot.handlers import callbacks, start, url_handler


@pytest.fixture
def mock_message():
    """Мок сообщения Telegram."""
    message = Mock(spec=Message)
    message.from_user = Mock(spec=User)
    message.from_user.id = 123
    message.from_user.username = 'testuser'
    message.chat = Mock(spec=Chat)
    message.chat.id = 123
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_cmd_start(mock_message) -> None:
    """Команда /start."""
    await start.cmd_start(mock_message)
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_help(mock_message) -> None:
    """Команда /help."""
    await start.cmd_help(mock_message)
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_message_with_url(
    mock_message,
) -> None:
    """Сообщение с URL."""
    mock_message.text = 'https://test.com/article'
    mock_state = AsyncMock()
    mock_state.get_data = AsyncMock(return_value={})

    mock_orch = AsyncMock()
    mock_orch.classifier.classify = AsyncMock()
    mock_orch.classifier.classify.return_value = (
        Mock(requires_auth=False)
    )

    with (
        patch(
            'bot.handlers.url_handler.is_valid_url',
            return_value=True,
        ),
        patch(
            'bot.handlers.url_handler.normalize_url',
            return_value=(
                'https://test.com/article'
            ),
        ),
        patch(
            'bot.handlers.url_handler'
            '._get_orchestrator',
            return_value=mock_orch,
        ),
        patch(
            'bot.handlers.url_handler'
            '.process_url_with_account',
        ) as mock_process,
    ):
        await url_handler.handle_message(
            mock_message, mock_state,
        )
        mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_handle_message_no_url(
    mock_message,
) -> None:
    """Сообщение без URL."""
    mock_message.text = 'просто текст'
    mock_state = AsyncMock()

    await url_handler.handle_message(
        mock_message, mock_state,
    )

    mock_message.answer.assert_called_once()
    call_text = (
        mock_message.answer.call_args[0][0]
    )
    assert 'не нашёл ссылку' in call_text


@pytest.mark.asyncio
async def test_auth_yes_callback(
    mock_message,
) -> None:
    """Callback 'у меня есть аккаунт'."""
    callback = Mock()
    callback.message = mock_message
    callback.from_user.id = 123
    callback.from_user.username = 'testuser'
    callback.answer = AsyncMock()

    mock_state = AsyncMock()
    mock_state.get_data = AsyncMock(
        return_value={'url': 'https://test.com'},
    )

    with patch(
        'bot.handlers.url_handler'
        '.process_url_with_account',
    ) as mock_process:
        await callbacks.auth_yes(
            callback, mock_state,
        )
        mock_process.assert_called_once()
        callback.answer.assert_called_once()
