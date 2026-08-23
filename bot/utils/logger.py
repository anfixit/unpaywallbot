"""Настройка логирования для всего приложения.

Обеспечивает единый формат логов, запись в файл
и консоль, ротацию логов по дням.

QueueHandler + QueueListener гарантируют, что
файловый I/O не блокирует asyncio event loop (§17.1).

QueueHandler ставится на root-логгер, поэтому в файл
попадают записи всех модулей, которые используют
``logging.getLogger(__name__)`` без собственной
настройки. Шумные сторонние библиотеки ограничены
уровнем WARNING.
"""

import logging
import sys
from logging.handlers import (
    QueueHandler,
    QueueListener,
    TimedRotatingFileHandler,
)
from pathlib import Path
from queue import Queue
from typing import Final

__all__ = ['setup_logger', 'shutdown_logging']

_LOG_FORMAT = (
    '%(asctime)s | %(levelname)-8s '
    '| %(name)s:%(lineno)d | %(message)s'
)
_LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
_BACKUP_COUNT = 30  # храним месяц логов

# Библиотеки, чей INFO/DEBUG не нужен в логах бота.
_NOISY_LIBRARIES: Final[tuple[str, ...]] = (
    'aiogram',
    'asyncio',
    'charset_normalizer',
    'httpcore',
    'httpx',
    'playwright',
    'redis',
    'urllib3',
)

# Единственный QueueListener на всё приложение.
# Инициализируется лениво при первом вызове
# setup_logger() — не при импорте (§21.5).
_listener: QueueListener | None = None
_queue: Queue[logging.LogRecord] | None = None
_handler: QueueHandler | None = None
_initialized = False


def _get_log_level() -> int:
    """Получить уровень логирования из settings."""
    from bot.config import settings

    return getattr(
        logging,
        settings.log_level.upper(),
        logging.INFO,
    )


def _get_log_dir() -> Path:
    """Получить директорию для логов."""
    log_dir = (
        Path(__file__).parent.parent.parent
        / 'data'
        / 'logs'
    )
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return log_dir


def _init_queue_logging() -> None:
    """Инициализировать QueueListener один раз.

    Файловый и консольный хендлеры работают
    в потоке QueueListener, не в event loop.
    """
    global _listener, _queue, _handler, _initialized  # noqa: PLW0603

    if _initialized:
        return

    log_queue: Queue[logging.LogRecord] = Queue(-1)
    _queue = log_queue
    log_level = _get_log_level()
    log_dir = _get_log_dir()

    formatter = logging.Formatter(
        _LOG_FORMAT, datefmt=_LOG_DATE_FORMAT,
    )

    # Консольный хендлер
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(log_level)

    # Файловый хендлер с ротацией по дням
    file_handler = TimedRotatingFileHandler(
        log_dir / 'bot.log',
        when='midnight',
        interval=1,
        backupCount=_BACKUP_COUNT,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    _listener = QueueListener(
        log_queue,
        console,
        file_handler,
        respect_handler_level=True,
    )
    _listener.start()

    # Root-хендлер: записи из всех модулей приложения
    # доходят до очереди через propagate.
    queue_handler = QueueHandler(log_queue)
    _handler = queue_handler

    root = logging.getLogger()
    root.addHandler(queue_handler)
    root.setLevel(log_level)

    for library in _NOISY_LIBRARIES:
        logging.getLogger(library).setLevel(
            max(log_level, logging.WARNING),
        )

    _initialized = True


def setup_logger(name: str) -> logging.Logger:
    """Настроить логирование и получить логгер.

    Хендлер живёт на root-логгере, поэтому модулям
    достаточно обычного ``logging.getLogger(__name__)``.
    Эта функция нужна точкам входа, чтобы
    инициализировать очередь до первой записи.

    Args:
        name: Имя логгера (обычно __name__).

    Returns:
        Настроенный логгер.
    """
    _init_queue_logging()
    return logging.getLogger(name)


def shutdown_logging() -> None:
    """Остановить QueueListener при завершении.

    Вызывается из main() при graceful shutdown.
    """
    global _listener, _queue, _handler, _initialized  # noqa: PLW0603

    if _handler is not None:
        logging.getLogger().removeHandler(_handler)
        _handler = None

    if _listener is not None:
        _listener.stop()
        _listener = None

    _queue = None
    _initialized = False
