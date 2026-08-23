"""Тесты настройки логирования."""

import logging
from pathlib import Path

import pytest

from bot.utils import logger as logger_module


@pytest.fixture
def log_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Изолированная директория логов."""
    target = tmp_path / 'logs'
    monkeypatch.setattr(
        logger_module,
        '_get_log_dir',
        lambda: (target.mkdir(parents=True, exist_ok=True), target)[1],
    )
    logger_module.shutdown_logging()
    yield target
    logger_module.shutdown_logging()


def _read_log(log_dir: Path) -> str:
    """Прочитать содержимое bot.log."""
    return (log_dir / 'bot.log').read_text(encoding='utf-8')


def test_module_logger_reaches_log_file(log_dir) -> None:
    """Модуль без setup_logger пишет в общий файл."""
    logger_module.setup_logger('bot.main')

    logging.getLogger(
        'bot.services.orchestrator',
    ).info('извлечение начато')

    logger_module.shutdown_logging()

    content = _read_log(log_dir)
    assert 'извлечение начато' in content
    assert 'bot.services.orchestrator' in content


def test_entrypoint_logger_is_not_duplicated(log_dir) -> None:
    """Запись точки входа появляется в файле один раз."""
    entry_logger = logger_module.setup_logger('bot.main')
    logger_module.setup_logger('bot.main')

    entry_logger.info('единственная запись')
    logger_module.shutdown_logging()

    content = _read_log(log_dir)
    assert content.count('единственная запись') == 1


def test_noisy_library_info_is_suppressed(log_dir) -> None:
    """INFO сторонних библиотек не засоряет лог."""
    logger_module.setup_logger('bot.main')

    logging.getLogger('httpx').info('HTTP Request: GET ...')
    logging.getLogger('httpx').warning('httpx предупреждение')

    logger_module.shutdown_logging()

    content = _read_log(log_dir)
    assert 'HTTP Request' not in content
    assert 'httpx предупреждение' in content


def test_shutdown_removes_root_handler(log_dir) -> None:
    """shutdown_logging не оставляет хендлер на root."""
    before = len(logging.getLogger().handlers)
    logger_module.setup_logger('bot.main')
    assert len(logging.getLogger().handlers) == before + 1

    logger_module.shutdown_logging()

    assert len(logging.getLogger().handlers) == before
