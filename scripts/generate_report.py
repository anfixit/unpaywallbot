#!/usr/bin/env python
"""Скрипт для генерации отчёта по логам.

Анализирует JSON-логи и выдаёт статистику
для диплома.

Запуск::

    uv run python -m scripts.generate_report --days 7
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bot.utils.logger import setup_logger

logger = setup_logger(__name__)

_DEFAULT_LOG_DIR = Path('data/logs')
_DEFAULT_DAYS = 7


def _load_logs(
    log_dir: Path,
    cutoff: datetime,
) -> list[dict]:
    """Загрузить логи новее cutoff.

    Args:
        log_dir: Директория с логами.
        cutoff: Минимальная дата файла.

    Returns:
        Список записей из JSONL-файлов.
    """
    log_files = sorted(log_dir.glob('access_*.jsonl'))
    records: list[dict] = []

    for log_file in log_files:
        try:
            date_str = log_file.stem.replace(
                'access_', '',
            )
            file_date = datetime.strptime(
                date_str, '%Y-%m-%d',
            ).replace(tzinfo=UTC)

            if file_date < cutoff:
                continue

            with open(
                log_file, encoding='utf-8',
            ) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(
                            json.loads(line),
                        )

        except (ValueError, json.JSONDecodeError):
            logger.warning(
                'Пропущен файл: %s', log_file,
            )

    return records


def _print_user_stats(logs: list[dict]) -> None:
    """Статистика по пользователям."""
    users = Counter(
        log['user_id']
        for log in logs
        if 'user_id' in log
    )
    logger.info(
        'Уникальных пользователей: %d', len(users),
    )
    logger.info('Топ-5 активных:')
    for uid, count in users.most_common(5):
        logger.info('  - %s: %d запросов', uid, count)


def _print_success_stats(logs: list[dict]) -> None:
    """Статистика успешности."""
    success = sum(
        1 for log in logs
        if log.get('status') == 'success'
    )
    errors = sum(
        1 for log in logs
        if log.get('status') == 'error'
    )
    rate = (
        (success / len(logs)) * 100
        if logs else 0
    )
    logger.info(
        'Успешно: %d (%.1f%%)', success, rate,
    )
    logger.info('Ошибок: %d', errors)


def _print_paywall_stats(logs: list[dict]) -> None:
    """Статистика по типам paywall."""
    types: Counter = Counter()
    for log in logs:
        pw = log.get('paywall')
        if pw and 'type' in pw:
            types[pw['type']] += 1

    if not types:
        return

    total = sum(types.values())
    logger.info('Типы paywall:')
    for ptype, count in types.most_common():
        pct = (count / total) * 100
        logger.info(
            '  - %s: %d (%.1f%%)',
            ptype, count, pct,
        )


def _print_duration_stats(logs: list[dict]) -> None:
    """Статистика по времени ответа."""
    durations = [
        log['duration_ms']
        for log in logs
        if 'duration_ms' in log
    ]
    if not durations:
        return

    avg = sum(durations) / len(durations)
    logger.info(
        'Среднее время ответа: %.0f мс', avg,
    )
    logger.info(
        'Максимальное: %.0f мс', max(durations),
    )


def _print_errors_by_day(logs: list[dict]) -> None:
    """Ошибки по дням."""
    by_day: dict[str, int] = defaultdict(int)
    for log in logs:
        if log.get('status') == 'error':
            day = log.get('timestamp', '')[:10]
            if day:
                by_day[day] += 1

    if not by_day:
        return

    logger.info('Ошибки по дням:')
    for day, count in sorted(by_day.items()):
        logger.info('  - %s: %d', day, count)


def analyze_logs(
    log_dir: Path = _DEFAULT_LOG_DIR,
    days: int = _DEFAULT_DAYS,
) -> None:
    """Проанализировать логи за последние N дней.

    Args:
        log_dir: Директория с логами.
        days: Количество дней для анализа.
    """
    if not log_dir.exists():
        logger.error('Директория не найдена: %s', log_dir)
        return

    cutoff = datetime.now(UTC) - timedelta(days=days)
    logs = _load_logs(log_dir, cutoff)

    logger.info(
        'Анализ логов за последние %d дней', days,
    )
    logger.info('Записей: %d', len(logs))

    if not logs:
        logger.info('Нет данных за указанный период')
        return

    _print_user_stats(logs)
    _print_success_stats(logs)
    _print_paywall_stats(logs)
    _print_duration_stats(logs)
    _print_errors_by_day(logs)


def _parse_args() -> argparse.Namespace:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Генерация отчёта по логам',
    )
    parser.add_argument(
        '--days',
        type=int,
        default=_DEFAULT_DAYS,
        help='Количество дней для анализа',
    )
    parser.add_argument(
        '--log-dir',
        type=Path,
        default=_DEFAULT_LOG_DIR,
        help='Директория с логами',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    analyze_logs(args.log_dir, args.days)
