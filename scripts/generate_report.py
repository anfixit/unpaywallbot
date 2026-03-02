#!/usr/bin/env python
"""Скрипт для генерации отчёта по логам.

Анализирует JSON-логи и выдаёт статистику для диплома.
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.utils.logger import setup_logger

logger = setup_logger(__name__)


def analyze_logs(log_dir: Path = Path('data/logs'), days: int = 7):
    """Проанализировать логи за последние N дней."""
    log_files = sorted(log_dir.glob('access_*.jsonl'))

    if not log_files:
        print('❌ Логи не найдены')
        return

    # Фильтруем по дате
    cutoff = datetime.now() - timedelta(days=days)
    recent_logs = []

    for log_file in log_files:
        # Извлекаем дату из имени файла access_2026-03-02.jsonl
        try:
            file_date = datetime.strptime(log_file.stem.replace('access_', ''), '%Y-%m-%d')
            if file_date >= cutoff:
                with open(log_file, encoding='utf-8') as f:
                    for line in f:
                        recent_logs.append(json.loads(line))
        except (ValueError, IndexError, json.JSONDecodeError):
            continue

    print(f'\n📊 Анализ логов за последние {days} дней')
    print(f'📁 Файлов: {len(log_files)}')
    print(f'📝 Записей: {len(recent_logs)}\n')

    if not recent_logs:
        print('Нет данных за указанный период')
        return

    # Статистика по пользователям
    users = Counter(log['user_id'] for log in recent_logs if 'user_id' in log)
    print(f'👥 Уникальных пользователей: {len(users)}')
    print('   Топ-5 активных:')
    for user_id, count in users.most_common(5):
        print(f'     - {user_id}: {count} запросов')

    # Успешность
    success = sum(1 for log in recent_logs if log.get('status') == 'success')
    errors = sum(1 for log in recent_logs if log.get('status') == 'error')
    success_rate = (success / len(recent_logs)) * 100 if recent_logs else 0
    print(f'\n✅ Успешно: {success} ({success_rate:.1f}%)')
    print(f'❌ Ошибок: {errors}')

    # Типы событий
    event_types = Counter(log['event_type'] for log in recent_logs)
    print('\n📨 Типы событий:')
    for event_type, count in event_types.most_common():
        print(f'   - {event_type}: {count}')

    # Paywall типы
    paywall_types = Counter()
    for log in recent_logs:
        if 'paywall' in log and log['paywall'] and 'type' in log['paywall']:
            paywall_types[log['paywall']['type']] += 1

    if paywall_types:
        print('\n🔒 Типы paywall:')
        total = sum(paywall_types.values())
        for ptype, count in paywall_types.most_common():
            pct = (count / total) * 100
            print(f'   - {ptype}: {count} ({pct:.1f}%)')

    # Среднее время ответа
    durations = [log['duration_ms'] for log in recent_logs if 'duration_ms' in log]
    if durations:
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        print(f'\n⏱️  Среднее время ответа: {avg_duration:.0f} мс')
        print(f'   Максимальное: {max_duration:.0f} мс')

    # Ошибки по дням
    errors_by_day = defaultdict(int)
    for log in recent_logs:
        if log.get('status') == 'error':
            day = log['timestamp'][:10]  # YYYY-MM-DD
            errors_by_day[day] += 1

    if errors_by_day:
        print('\n📆 Ошибки по дням:')
        for day, count in sorted(errors_by_day.items()):
            print(f'   - {day}: {count}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Генерация отчёта по логам')
    parser.add_argument('--days', type=int, default=7, help='Количество дней для анализа')
    parser.add_argument('--log-dir', type=Path, default=Path('data/logs'), help='Директория с логами')

    args = parser.parse_args()
    analyze_logs(args.log_dir, args.days)
