#!/usr/bin/env python
"""Скрипт для регистрации аккаунтов в менеджере.

Использование:
    python scripts/register_accounts.py --domain nytimes.com --email user@example.com --password pass123
    python scripts/register_accounts.py --domain spiegel.de --email user@example.com --password pass123 --shared
"""

import argparse
import asyncio

# Добавляем корневую директорию в путь для импорта
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.auth.account_manager import Account, AccountManager
from bot.utils.logger import setup_logger

logger = setup_logger(__name__)


async def main():
    parser = argparse.ArgumentParser(description='Регистрация аккаунтов')
    parser.add_argument('--domain', required=True, help='Домен сайта')
    parser.add_argument('--email', required=True, help='Email для входа')
    parser.add_argument('--password', required=True, help='Пароль')
    parser.add_argument('--user-id', type=int, help='ID пользователя Telegram (если личный)')
    parser.add_argument('--shared', action='store_true', help='Общий аккаунт для всех')

    args = parser.parse_args()

    # Создаём аккаунт
    account = Account(
        email=args.email,
        password=args.password,
        domain=args.domain,
        user_id=args.user_id if args.user_id else (0 if args.shared else None),
        is_active=True,
    )

    # Сохраняем
    storage_path = Path('data/sessions/accounts.json')
    manager = AccountManager(storage_path)

    if args.shared:
        await manager.add_account(account)
        logger.info(f'Добавлен общий аккаунт для {args.domain}')
    elif args.user_id:
        await manager.add_account(account, for_user=args.user_id)
        logger.info(f'Добавлен личный аккаунт для пользователя {args.user_id}')
    else:
        logger.error('Укажите --user-id или --shared')
        return

    # Проверяем
    test_url = f'https://{args.domain}/test'
    if args.user_id:
        retrieved = await manager.get_account_for_url(test_url, args.user_id)
    else:
        retrieved = await manager.get_account_for_url(test_url, 999)  # любой пользователь

    if retrieved:
        logger.info('✓ Аккаунт успешно сохранён и доступен')
    else:
        logger.error('✗ Ошибка: аккаунт не найден после сохранения')


if __name__ == '__main__':
    asyncio.run(main())
