"""Тесты отчёта по access-логам."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from scripts.generate_report import analyze_logs

_MODULE = 'scripts.generate_report'


def _write_log(log_dir: Path, records: list[dict]) -> None:
    """Записать JSONL-файл за сегодняшнюю дату."""
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime('%Y-%m-%d')
    path = log_dir / f'access_{today}.jsonl'
    path.write_text(
        '\n'.join(
            json.dumps(record, ensure_ascii=False)
            for record in records
        ),
        encoding='utf-8',
    )


def test_report_counts_pseudonymous_users(
    tmp_path,
    caplog,
) -> None:
    """Отчёт считает пользователей по user_hash."""
    _write_log(
        tmp_path / 'logs',
        [
            {
                'user_hash': 'abc123',
                'status': 'success',
                'duration_ms': 100.0,
                'paywall': {
                    'domain': 'spiegel.de',
                    'type': 'freemium',
                },
            },
            {
                'user_hash': 'abc123',
                'status': 'success',
                'duration_ms': 150.0,
            },
            {
                'user_hash': 'def456',
                'status': 'error',
                'duration_ms': 90.0,
            },
        ],
    )

    with caplog.at_level(logging.INFO, logger=_MODULE):
        analyze_logs(tmp_path / 'logs', days=1)

    output = '\n'.join(
        record.getMessage() for record in caplog.records
    )
    assert 'Уникальных пользователей: 2' in output
    assert 'abc123: 2 запросов' in output
    assert 'freemium' in output


def test_report_supports_raw_identifiers(
    tmp_path,
    caplog,
) -> None:
    """Формат с raw user_id тоже поддерживается."""
    _write_log(
        tmp_path / 'logs',
        [
            {
                'user_id': 123,
                'status': 'success',
                'duration_ms': 10.0,
            },
        ],
    )

    with caplog.at_level(logging.INFO, logger=_MODULE):
        analyze_logs(tmp_path / 'logs', days=1)

    output = '\n'.join(
        record.getMessage() for record in caplog.records
    )
    assert 'Уникальных пользователей: 1' in output
