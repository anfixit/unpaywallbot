"""Настройка логирования для всего приложения.

Обеспечивает единый формат логов, запись в файл
и консоль, ротацию логов по дням.

QueueHandler + QueueListener гарантируют, что
файловый I/O не блокирует asyncio event loop (§17.1).
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

__all__ = ['setup_logger', 'shutdown_logging']

_LOG_FORMAT = (
    '%(asctime)s | %(levelname)-8s '
    '| %(name)s:%(lineno)d | %(message)s'
)
_LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
_BACKUP_COUNT = 30  # храним месяц логов

# Единственный QueueListener на всё приложение.
# Инициализируется лениво при первом вызове
# setup_logger() — не при импорте (§21.5).
_listener: QueueListener | None = None
_queue: Queue | None = None
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
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _init_queue_logging() -> None:
    """Инициализировать QueueListener один раз.

    Файловый и консольный хендлеры работают
    в потоке QueueListener, не в event loop.
    """
    global _listener, _queue, _initialized  # noqa: PLW0603

    if _initialized:
        return

    _queue = Queue(-1)
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
        _queue,
        console,
        file_handler,
        respect_handler_level=True,
    )
    _listener.start()
    _initialized = True


def setup_logger(name: str) -> logging.Logger:
    """Настроить и получить логгер.

    Все логгеры пишут через QueueHandler,
    фактический I/O — в потоке QueueListener.

    Args:
        name: Имя логгера (обычно __name__).

    Returns:
        Настроенный логгер.
    """
    _init_queue_logging()

    logger = logging.getLogger(name)

    # Предотвращаем добавление хендлеров повторно
    if logger.handlers:
        return logger

    log_level = _get_log_level()
    logger.setLevel(log_level)

    queue_handler = QueueHandler(_queue)
    logger.addHandler(queue_handler)

    # propagate=False — не дублируем через root
    logger.propagate = False

    return logger


def shutdown_logging() -> None:
    """Остановить QueueListener при завершении.

    Вызывается из main() при graceful shutdown.
    """
    global _listener, _initialized  # noqa: PLW0603

    if _listener is not None:
        _listener.stop()
        _listener = None
    _initialized = False
