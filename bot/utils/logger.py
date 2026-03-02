"""Настройка логирования для всего приложения.

Обеспечивает единый формат логов, запись в файл и консоль,
ротацию логов по дням.
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from bot.config import settings

__all__ = ['setup_logger']


def setup_logger(name: str, log_dir: Path | None = None) -> logging.Logger:
    """Настроить и получить логгер.

    Args:
        name: Имя логгера (обычно __name__).
        log_dir: Директория для логов (по умолчанию data/logs).

    Returns:
        Настроенный логгер.
    """
    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / 'data' / 'logs'

    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    # Предотвращаем добавление хендлеров повторно
    if logger.handlers:
        return logger

    # Уровень логирования из настроек
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Хендлер для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # Хендлер для файла с ротацией по дням
    file_handler = TimedRotatingFileHandler(
        log_dir / 'bot.log',
        when='midnight',
        interval=1,
        backupCount=30,  # храним месяц
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)

    # Отключаем propagation, чтобы логи не дублировались
    logger.propagate = False

    return logger
