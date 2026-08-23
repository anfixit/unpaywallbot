"""Тесты middleware."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.types import Chat, Message, User

from bot.constants import BypassMethod, PaywallType
from bot.middleware.access_log import AccessLogMiddleware
from bot.middleware.rate_limiter import RateLimiterMiddleware
from bot.middleware.whitelist import WhitelistMiddleware
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.models.user_request import UserRequest
from bot.utils.request_context import set_current_request


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
    message.message_id = 1
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

    mock_client = Mock()
    mock_client.eval = AsyncMock(return_value=0)
    mock_redis = Mock(client=mock_client)

    with patch(
        'bot.middleware.rate_limiter.get_redis_client',
        return_value=mock_redis,
    ):
        result = await middleware(
            mock_handler,
            mock_message,
            {},
        )

    assert result == 'ok'
    mock_handler.assert_called_once()
    mock_client.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_rate_limiter_blocked(
    mock_message,
    mock_handler,
) -> None:
    """Пользователь превысил минутный лимит."""
    middleware = RateLimiterMiddleware(
        rate_per_minute=5,
    )

    mock_client = Mock()
    mock_client.eval = AsyncMock(return_value=1)
    mock_redis = Mock(client=mock_client)

    with patch(
        'bot.middleware.rate_limiter.get_redis_client',
        return_value=mock_redis,
    ):
        result = await middleware(
            mock_handler,
            mock_message,
            {},
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
    middleware = WhitelistMiddleware(
        whitelist=[123],
        public_access=False,
    )

    result = await middleware(
        mock_handler,
        mock_message,
        {},
    )

    assert result == 'ok'
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_whitelist_blocked(
    mock_message,
    mock_handler,
) -> None:
    """Пользователь не в белом списке."""
    middleware = WhitelistMiddleware(
        whitelist=[456],
        public_access=False,
    )

    result = await middleware(
        mock_handler,
        mock_message,
        {},
    )

    assert result is None
    mock_handler.assert_not_called()
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_public_access(
    mock_message,
    mock_handler,
) -> None:
    """Явный public mode пропускает пользователя."""
    middleware = WhitelistMiddleware(
        whitelist=[],
        public_access=True,
    )

    result = await middleware(
        mock_handler,
        mock_message,
        {},
    )

    assert result == 'ok'


@pytest.mark.asyncio
async def test_access_log(
    mock_message,
    mock_handler,
    tmp_path,
) -> None:
    """Логирование запросов без raw identifiers."""
    middleware = AccessLogMiddleware(
        log_dir=tmp_path,
    )

    result = await middleware(
        mock_handler,
        mock_message,
        {},
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
    assert 'user_hash' in log_entry
    assert 'user_id' not in log_entry
    assert 'username' not in log_entry
    assert log_entry['status'] == 'success'
    assert 'duration_ms' in log_entry


@pytest.mark.asyncio
async def test_access_log_records_processing_metadata(
    mock_message,
    tmp_path,
) -> None:
    """Метаданные обработки попадают в access log."""
    request = UserRequest(
        user_id=123,
        original_url='https://spiegel.de/plus/article',
    )
    request.paywall_info = PaywallInfo(
        url=request.original_url,
        domain='spiegel.de',
        paywall_type=PaywallType.FREEMIUM,
        suggested_method=BypassMethod.JS_DISABLE,
    )
    request.complete(
        Article(
            url=request.original_url,
            content='Публичный текст',
        ),
    )

    async def handler(event, data):
        set_current_request(request)
        return 'ok'

    middleware = AccessLogMiddleware(log_dir=tmp_path)
    await middleware(handler, mock_message, {})

    log_file = next(tmp_path.glob('access_*.jsonl'))
    entry = json.loads(
        log_file.read_text(encoding='utf-8').strip(),
    )

    assert entry['paywall']['domain'] == 'spiegel.de'
    assert entry['paywall']['type'] == 'freemium'
    assert entry['paywall']['method'] == 'js_disable'
    assert entry['article']['content_length'] == len(
        'Публичный текст',
    )
    # Приватные поля в лог не попадают.
    assert 'url' not in entry
    assert 'user_id' not in entry


@pytest.mark.asyncio
async def test_access_log_ignores_stale_request(
    mock_message,
    mock_handler,
    tmp_path,
) -> None:
    """Контекст прошлого апдейта не переносится в новый."""
    stale = UserRequest(
        user_id=999,
        original_url='https://old.example.com/a',
    )
    stale.paywall_info = PaywallInfo(
        url=stale.original_url,
        domain='old.example.com',
        paywall_type=PaywallType.SOFT,
    )
    set_current_request(stale)

    middleware = AccessLogMiddleware(log_dir=tmp_path)
    await middleware(mock_handler, mock_message, {})

    log_file = next(tmp_path.glob('access_*.jsonl'))
    entry = json.loads(
        log_file.read_text(encoding='utf-8').strip(),
    )

    assert 'paywall' not in entry
