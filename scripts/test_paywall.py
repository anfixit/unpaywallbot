#!/usr/bin/env python
"""Скрипт для тестирования конкретного URL.

Позволяет быстро проверить, как бот обрабатывает заданную статью.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.services.orchestrator import Orchestrator
from bot.utils.logger import setup_logger
from bot.utils.text_formatter import truncate_with_ellipsis

logger = setup_logger(__name__)


async def test_url(url: str, user_id: int = 123, verbose: bool = False):
    """Протестировать обработку URL."""
    print(f'\n🔍 Тестируем URL: {url}\n')

    orchestrator = Orchestrator()

    # Классификация
    print('📋 Классификация...')
    paywall_info = await orchestrator.classifier.classify(url)
    print(f'   Домен: {paywall_info.domain}')
    print(f'   Тип: {paywall_info.paywall_type}')
    print(f'   Метод: {paywall_info.suggested_method}')
    print(f'   Платформа: {paywall_info.platform}')
    print(f'   Требует авторизации: {paywall_info.requires_auth}')
    print()

    # Получение статьи
    print('📥 Получение статьи...')
    request = await orchestrator.process_url(
        url=url,
        user_id=user_id,
        username='test_user',
        skip_cache=True,  # всегда свежий запрос для теста
    )

    if request.success and request.article:
        print('✅ Успешно!')
        article = request.article
        print(f'   Заголовок: {article.title}')
        print(f'   Автор: {article.author}')
        print(f'   Длина текста: {len(article.content)} символов')
        print(f'   Метод: {article.extraction_method}')

        if verbose and article.content:
            print('\n📄 Превью текста:')
            print('─' * 50)
            print(truncate_with_ellipsis(article.content, 500))
            print('─' * 50)
    else:
        print('❌ Ошибка!')
        print(f'   {request.error_message}')

    # Статистика времени
    if request.processing_time_ms:
        print(f'\n⏱️  Время обработки: {request.processing_time_ms:.0f} мс')

    return request


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Тестирование paywall')
    parser.add_argument('url', help='URL статьи для тестирования')
    parser.add_argument('--user-id', type=int, default=123, help='ID пользователя (для авторизации)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Показать превью текста')

    args = parser.parse_args()

    asyncio.run(test_url(args.url, args.user_id, args.verbose))
