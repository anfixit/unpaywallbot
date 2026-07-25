#!/usr/bin/env python
"""Безопасно добавить аккаунт в encrypted storage.

Интерактивный запуск::

    uv run python -m scripts.register_accounts \
        --domain example.com \
        --email user@example.com \
        --shared

Для автоматизации пароль можно передать через stdin::

    printf '%s\n' "$ACCOUNT_PASSWORD" | \
        uv run python -m scripts.register_accounts \
        --domain example.com \
        --email user@example.com \
        --user-id 123 \
        --password-stdin
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from bot.auth.account_manager import (
    Account,
    AccountManager,
)
from bot.utils.logger import setup_logger
from bot.utils.url_utils import extract_domain, normalize_url

logger = setup_logger(__name__)

_DEFAULT_STORAGE = Path('data/sessions/accounts.json')


def _normalize_domain(value: str) -> str:
    """Проверить домен и убрать схему или путь."""
    candidate = value.strip()
    if '://' not in candidate:
        candidate = f'https://{candidate}'
    normalized = normalize_url(candidate)
    domain = extract_domain(normalized)
    if not domain or '.' not in domain:
        msg = f'Некорректный домен: {value!r}'
        raise ValueError(msg)
    return domain


def _read_password(*, from_stdin: bool) -> str:
    """Получить пароль без аргумента командной строки."""
    if from_stdin:
        password = sys.stdin.readline().rstrip('\r\n')
    else:
        password = getpass.getpass('Пароль аккаунта: ')

    if not password:
        msg = 'Пароль не может быть пустым'
        raise ValueError(msg)
    return password


async def register_account(
    args: argparse.Namespace,
    password: str,
) -> bool:
    """Зарегистрировать и проверить аккаунт."""
    domain = _normalize_domain(args.domain)
    email = args.email.strip()
    if not email:
        msg = 'Email не может быть пустым'
        raise ValueError(msg)

    user_id = args.user_id if args.user_id is not None else 0
    account = Account(
        email=email,
        password=password,
        domain=domain,
        user_id=user_id,
        is_active=True,
    )

    manager = AccountManager(args.storage)
    if args.shared:
        await manager.add_account(account)
        logger.info(
            'Добавлен общий аккаунт для %s',
            domain,
        )
    else:
        await manager.add_account(
            account,
            for_user=args.user_id,
        )
        logger.info(
            'Добавлен личный аккаунт для пользователя %d',
            args.user_id,
        )

    retrieved = await manager.get_account_for_url(
        f'https://{domain}/',
        args.user_id or 1,
    )
    if retrieved is None:
        logger.error('Аккаунт не найден после сохранения')
        return False

    logger.info(
        'Аккаунт сохранён в %s',
        args.storage,
    )
    return True


def _parse_args() -> argparse.Namespace:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Регистрация encrypted account',
    )
    parser.add_argument(
        '--domain',
        required=True,
        help='Домен сайта',
    )
    parser.add_argument(
        '--email',
        required=True,
        help='Email для входа',
    )
    parser.add_argument(
        '--storage',
        type=Path,
        default=_DEFAULT_STORAGE,
        help='Путь к encrypted storage',
    )
    parser.add_argument(
        '--password-stdin',
        action='store_true',
        help='Прочитать пароль из первой строки stdin',
    )

    owner = parser.add_mutually_exclusive_group(
        required=True,
    )
    owner.add_argument(
        '--user-id',
        type=int,
        help='ID пользователя Telegram',
    )
    owner.add_argument(
        '--shared',
        action='store_true',
        help='Общий аккаунт для всех',
    )
    return parser.parse_args()


def main() -> int:
    """Запустить CLI и вернуть exit code."""
    args = _parse_args()
    try:
        password = _read_password(
            from_stdin=args.password_stdin,
        )
        saved = asyncio.run(
            register_account(args, password),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        logger.error('Аккаунт не сохранён: %s', exc)
        return 1
    return 0 if saved else 1


if __name__ == '__main__':
    raise SystemExit(main())
