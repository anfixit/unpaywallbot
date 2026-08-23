"""Тесты для Telegram-хендлеров."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.types import Chat, Message, User

from bot.constants import MAX_MESSAGE_LENGTH
from bot.handlers import callbacks, start, url_handler
from bot.models.article import Article
from bot.models.user_request import UserRequest
from bot.utils.request_context import (
    clear_current_request,
    get_current_request,
)


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
    """Сообщение с URL без requires_auth."""
    mock_message.text = 'https://test.com/article'
    mock_state = AsyncMock()
    mock_state.get_data = AsyncMock(return_value={})

    mock_orch = AsyncMock()
    mock_orch.classifier.classify = AsyncMock(
        return_value=Mock(requires_auth=False),
    )

    with (
        patch(
            'bot.handlers.url_handler.is_valid_url',
            return_value=True,
        ),
        patch(
            'bot.handlers.url_handler.normalize_url',
            return_value='https://test.com/article',
        ),
        patch(
            'bot.handlers.url_handler._get_orchestrator',
            return_value=mock_orch,
        ),
        patch(
            'bot.handlers.url_handler.process_url_message',
        ) as mock_process,
    ):
        await url_handler.handle_message(
            mock_message,
            mock_state,
        )

    mock_process.assert_awaited_once_with(
        message=mock_message,
        url='https://test.com/article',
        user_id=123,
        state=mock_state,
    )


@pytest.mark.asyncio
async def test_handle_message_no_url(
    mock_message,
) -> None:
    """Сообщение без URL."""
    mock_message.text = 'просто текст'
    mock_state = AsyncMock()

    await url_handler.handle_message(
        mock_message,
        mock_state,
    )

    mock_message.answer.assert_called_once()
    call_text = str(mock_message.answer.call_args)
    assert 'ссылк' in call_text.lower()


@pytest.mark.asyncio
async def test_try_anyway_callback(
    mock_message,
) -> None:
    """Callback попробует публичные способы."""
    callback = Mock()
    callback.message = mock_message
    callback.from_user = Mock()
    callback.from_user.id = 123
    callback.from_user.username = 'testuser'
    callback.answer = AsyncMock()
    callback.data = 'try_anyway'

    mock_state = AsyncMock()
    mock_state.get_data = AsyncMock(
        return_value={'url': 'https://test.com'},
    )

    with patch(
        'bot.handlers.callbacks.process_url_message',
        new=AsyncMock(),
    ) as mock_process:
        await callbacks.try_anyway(
            callback,
            mock_state,
        )

    mock_process.assert_awaited_once_with(
        message=mock_message,
        url='https://test.com',
        user_id=123,
        state=mock_state,
    )
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_retry_archives_callback(
    mock_message,
) -> None:
    """Повторная проверка продолжает сохранённый запрос."""
    callback = Mock()
    callback.message = mock_message
    callback.from_user = Mock()
    callback.from_user.id = 123
    callback.answer = AsyncMock()

    mock_state = AsyncMock()
    mock_state.get_data = AsyncMock(
        return_value={'url': 'https://test.com/article'},
    )

    with patch(
        'bot.handlers.callbacks.process_url_message',
        new=AsyncMock(),
    ) as mock_process:
        await callbacks.retry_archives(callback, mock_state)

    callback.answer.assert_awaited_once()
    mock_process.assert_awaited_once_with(
        message=mock_message,
        url='https://test.com/article',
        user_id=123,
        state=mock_state,
    )


@pytest.mark.asyncio
async def test_process_url_keeps_telegraph_disabled(
    mock_message,
) -> None:
    """Не передавать статью третьей стороне по умолчанию."""
    status_message = Mock(spec=Message)
    status_message.delete = AsyncMock()
    mock_message.answer = AsyncMock(
        side_effect=[status_message, None, None],
    )
    mock_state = AsyncMock()
    request = UserRequest(
        user_id=123,
        original_url='https://example.com/article',
    )
    request.complete(
        Article(
            url='https://example.com/article',
            title='Article',
            content='Public text',
        ),
    )
    orchestrator = AsyncMock()
    orchestrator.process_url = AsyncMock(
        return_value=request,
    )

    with (
        patch.object(
            url_handler.settings,
            'telegraph_enabled',
            False,
        ),
        patch(
            'bot.handlers.url_handler._get_orchestrator',
            return_value=orchestrator,
        ),
        patch(
            'bot.handlers.url_handler'
            '._get_telegraph_publisher',
        ) as get_publisher,
    ):
        await url_handler.process_url_message(
            message=mock_message,
            url='https://example.com/article',
            user_id=123,
            state=mock_state,
        )

    orchestrator.process_url.assert_awaited_once_with(
        url='https://example.com/article',
        user_id=123,
        skip_cache=False,
    )
    mock_state.clear.assert_awaited_once()
    get_publisher.assert_not_called()


@pytest.mark.asyncio
async def test_long_article_parts_fit_telegram_limit(
    mock_message,
) -> None:
    """Каждая часть с заголовком укладывается в лимит."""
    status_message = Mock(spec=Message)
    status_message.delete = AsyncMock()
    sent: list[str] = []

    async def answer(text, **kwargs):
        if not sent:
            sent.append(text)
            return status_message
        sent.append(text)
        return None

    mock_message.answer = AsyncMock(side_effect=answer)
    mock_state = AsyncMock()

    request = UserRequest(
        user_id=123,
        original_url='https://example.com/long',
    )
    request.complete(
        Article(
            url='https://example.com/long',
            title='Длинная статья',
            content='слово ' * 4000,
        ),
    )
    orchestrator = AsyncMock()
    orchestrator.process_url = AsyncMock(
        return_value=request,
    )

    with (
        patch.object(
            url_handler.settings,
            'telegraph_enabled',
            False,
        ),
        patch(
            'bot.handlers.url_handler._get_orchestrator',
            return_value=orchestrator,
        ),
    ):
        await url_handler.process_url_message(
            message=mock_message,
            url='https://example.com/long',
            user_id=123,
            state=mock_state,
        )

    parts = [
        text for text in sent
        if text.startswith('📄 Часть')
    ]
    assert len(parts) > 1
    assert all(
        len(text) <= MAX_MESSAGE_LENGTH for text in sent
    )


@pytest.mark.asyncio
async def test_process_url_publishes_request_context(
    mock_message,
) -> None:
    """Обработанный запрос доступен access log."""
    status_message = Mock(spec=Message)
    status_message.delete = AsyncMock()
    mock_message.answer = AsyncMock(
        side_effect=[status_message, None, None],
    )
    mock_state = AsyncMock()

    request = UserRequest(
        user_id=123,
        original_url='https://example.com/article',
    )
    request.complete(
        Article(
            url='https://example.com/article',
            content='Public text',
        ),
    )
    orchestrator = AsyncMock()
    orchestrator.process_url = AsyncMock(
        return_value=request,
    )

    clear_current_request()
    with (
        patch.object(
            url_handler.settings,
            'telegraph_enabled',
            False,
        ),
        patch(
            'bot.handlers.url_handler._get_orchestrator',
            return_value=orchestrator,
        ),
    ):
        await url_handler.process_url_message(
            message=mock_message,
            url='https://example.com/article',
            user_id=123,
            state=mock_state,
        )

    assert get_current_request() is request


@pytest.mark.asyncio
async def test_article_goes_to_telegraph_not_chat(
    mock_message,
) -> None:
    """Статья публикуется на telegra.ph, а не текстом."""
    status_message = Mock(spec=Message)
    status_message.delete = AsyncMock()
    sent: list[str] = []

    async def answer(text, **kwargs):
        sent.append(text)
        return status_message if len(sent) == 1 else None

    mock_message.answer = AsyncMock(side_effect=answer)

    request = UserRequest(
        user_id=123,
        original_url='https://zeit.de/article',
    )
    request.complete(
        Article(
            url='https://zeit.de/article',
            title='Статья',
            content='Короткий текст статьи.',
        ),
    )
    orchestrator = AsyncMock()
    orchestrator.process_url = AsyncMock(return_value=request)
    publisher = Mock()
    publisher.should_use_telegraph = Mock(return_value=True)
    publisher.publish = AsyncMock(
        return_value='https://telegra.ph/Test-01-01',
    )

    with (
        patch.object(
            url_handler.settings, 'telegraph_enabled', True,
        ),
        patch(
            'bot.handlers.url_handler._get_orchestrator',
            return_value=orchestrator,
        ),
        patch(
            'bot.handlers.url_handler._get_telegraph_publisher',
            return_value=publisher,
        ),
    ):
        await url_handler.process_url_message(
            message=mock_message,
            url='https://zeit.de/article',
            user_id=123,
            state=AsyncMock(),
        )

    publisher.publish.assert_awaited_once()
    result = sent[-1]
    assert 'telegra.ph/Test-01-01' in result
    # Текст статьи в чат не уходит.
    assert 'Короткий текст статьи.' not in result


@pytest.mark.asyncio
async def test_partial_article_is_labelled(
    mock_message,
) -> None:
    """Фрагмент помечается предупреждением."""
    status_message = Mock(spec=Message)
    status_message.delete = AsyncMock()
    sent: list[str] = []

    async def answer(text, **kwargs):
        sent.append(text)
        return status_message if len(sent) == 1 else None

    mock_message.answer = AsyncMock(side_effect=answer)

    request = UserRequest(
        user_id=123,
        original_url='https://welt.de/plus/a',
    )
    article = Article(
        url='https://welt.de/plus/a',
        title='Плюсовая статья',
        content='Анонс.',
    )
    article.is_partial = True
    request.complete(article)
    orchestrator = AsyncMock()
    orchestrator.process_url = AsyncMock(return_value=request)

    with (
        patch.object(
            url_handler.settings, 'telegraph_enabled', False,
        ),
        patch(
            'bot.handlers.url_handler._get_orchestrator',
            return_value=orchestrator,
        ),
    ):
        await url_handler.process_url_message(
            message=mock_message,
            url='https://welt.de/plus/a',
            user_id=123,
            state=AsyncMock(),
        )

    header = sent[1]
    assert 'только публичный фрагмент' in header
    assert 'без подписки' in header


@pytest.mark.asyncio
async def test_failure_offers_archive_link(
    mock_message,
) -> None:
    """При неудаче бот предлагает открыть архив вручную."""
    status_message = Mock(spec=Message)
    status_message.delete = AsyncMock()
    sent: list[tuple[str, dict]] = []

    async def answer(text, **kwargs):
        sent.append((text, kwargs))
        return status_message if len(sent) == 1 else None

    mock_message.answer = AsyncMock(side_effect=answer)

    request = UserRequest(
        user_id=123,
        original_url='https://welt.de/plus/a',
    )
    request.complete(error=RuntimeError('нет текста'))
    orchestrator = AsyncMock()
    orchestrator.process_url = AsyncMock(return_value=request)
    state = AsyncMock()

    with patch(
        'bot.handlers.url_handler._get_orchestrator',
        return_value=orchestrator,
    ):
        await url_handler.process_url_message(
            message=mock_message,
            url='https://welt.de/plus/a',
            user_id=123,
            state=state,
        )

    reply, kwargs = sent[-1]
    assert 'web.archive.org/web/*/' in reply
    assert 'Wayback Machine' in reply
    markup = kwargs['reply_markup']
    buttons = [
        button
        for row in markup.inline_keyboard
        for button in row
    ]
    assert any(button.callback_data == 'retry_archives' for button in buttons)
    assert any(
        button.url and 'web.archive.org/web/*/' in button.url
        for button in buttons
    )
    state.set_data.assert_awaited_once_with(
        {'url': 'https://welt.de/plus/a'},
    )
    state.clear.assert_not_awaited()
