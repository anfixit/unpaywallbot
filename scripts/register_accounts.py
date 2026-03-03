#!/usr/bin/env python
"""Скрипт для регистрации аккаунтов в менеджере.

Запуск::

    uv run python -m scripts.register_accounts \\
        --domain nytimes.com \\
        --email user@example.com \\
        --password pass123 --shared
"""

import argparse
import asyncio
from pathlib import Path

from bot.auth.account_manager import (
    Account,
    AccountManager,
)
from bot.utils.logger import setup_logger

logger = setup_logger(__name__)

_DEFAULT_STORAGE = Path('data/sessions/accounts.json')


async def register_account(
    args: argparse.Namespace,
) -> None:
    """Зарегистрировать аккаунт.

    Args:
        args: Аргументы командной строки.
    """
    user_id = args.user_id or (
        0 if args.shared else None
    )

    if user_id is None:
        logger.error(
            'Укажите --user-id или --shared',
        )
        return

    account = Account(
        email=args.email,
        password=args.password,
        domain=args.domain,
        user_id=user_id,
        is_active=True,
    )

    manager = AccountManager(_DEFAULT_STORAGE)

    if args.shared:
        await manager.add_account(account)
        logger.info(
            'Добавлен общий аккаунт для %s',
            args.domain,
        )
    else:
        await manager.add_account(
            account, for_user=args.user_id,
        )
        logger.info(
            'Добавлен личный аккаунт '
            'для пользователя %d',
            args.user_id,
        )

    # Проверяем
    test_url = f'https://{args.domain}/test'
    test_uid = args.user_id or 999
    retrieved = await manager.get_account_for_url(
        test_url, test_uid,
    )

    if retrieved:
        logger.info(
            'Аккаунт успешно сохранён и доступен',
        )
    else:
        logger.error(
            'Аккаунт не найден после сохранения',
        )


def _parse_args() -> argparse.Namespace:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Регистрация аккаунтов',
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
        '--password',
        required=True,
        help='Пароль',
    )
    parser.add_argument(
        '--user-id',
        type=int,
        help='ID пользователя Telegram',
    )
    parser.add_argument(
        '--shared',
        action='store_true',
        help='Общий аккаунт для всех',
    )
    return parser.parse_args()


if __name__ == '__main__':
    asyncio.run(register_account(_parse_args()))
