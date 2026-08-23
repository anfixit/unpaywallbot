"""Контекст текущего запроса для операционных логов.

Хендлер и AccessLogMiddleware выполняются в одной
asyncio-задаче, поэтому ContextVar позволяет передать
метаданные обработки в лог, не меняя сигнатуры
aiogram-хендлеров.

Хранятся только безопасные метаданные: домен, тип
paywall и метод извлечения. Ни URL, ни текст статьи,
ни raw Telegram identifiers сюда не попадают.
"""

from contextvars import ContextVar

from bot.models.user_request import UserRequest

__all__ = [
    'clear_current_request',
    'get_current_request',
    'set_current_request',
]

_current_request: ContextVar[UserRequest | None] = ContextVar(
    'current_request',
    default=None,
)


def set_current_request(request: UserRequest) -> None:
    """Запомнить обработанный запрос для текущего апдейта."""
    _current_request.set(request)


def get_current_request() -> UserRequest | None:
    """Вернуть запрос текущего апдейта, если он был."""
    return _current_request.get()


def clear_current_request() -> None:
    """Сбросить контекст перед обработкой апдейта."""
    _current_request.set(None)
