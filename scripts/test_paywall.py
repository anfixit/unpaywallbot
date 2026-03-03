#!/usr/bin/env python
"""Скрипт для тестирования конкретного URL.

Позволяет быстро проверить, как бот обрабатывает
заданную статью.

Запуск::

    uv run python -m scripts.test_paywall \\
        https://spiegel.de/plus/artikel -v
"""

import argparse
import asyncio

from bot.services.orchestrator import Orchestrator
from bot.utils.logger import setup_logger
from bot.utils.text_formatter import (
    truncate_with_ellipsis,
)

logger = setup_logger(__name__)

_DEFAULT_USER_ID = 123
_PREVIEW_LENGTH = 500
_SEPARATOR = '─' * 50


async def test_url(
    url: str,
    user_id: int = _DEFAULT_USER_ID,
    verbose: bool = False,
) -> None:
    """Протестировать обработку URL.

    Args:
        url: URL статьи для тестирования.
        user_id: ID пользователя (для авторизации).
        verbose: Показать превью текста.
    """
    logger.info('Тестируем URL: %s', url)

    orchestrator = Orchestrator()

    # Классификация
    logger.info('Классификация...')
    paywall_info = (
        await orchestrator.classifier.classify(url)
    )
    logger.info('  Домен: %s', paywall_info.domain)
    logger.info(
        '  Тип: %s', paywall_info.paywall_type,
    )
    logger.info(
        '  Метод: %s', paywall_info.suggested_method,
    )
    logger.info(
        '  Платформа: %s', paywall_info.platform,
    )
    logger.info(
        '  Требует авторизации: %s',
        paywall_info.requires_auth,
    )

    # Получение статьи
    logger.info('Получение статьи...')
    request = await orchestrator.process_url(
        url=url,
        user_id=user_id,
        username='test_user',
        skip_cache=True,
    )

    if request.success and request.article:
        article = request.article
        logger.info('Успешно!')
        logger.info('  Заголовок: %s', article.title)
        logger.info('  Автор: %s', article.author)
        logger.info(
            '  Длина текста: %d символов',
            len(article.content),
        )
        logger.info(
            '  Метод: %s',
            article.extraction_method,
        )

        if verbose and article.content:
            logger.info('Превью текста:')
            logger.info(_SEPARATOR)
            logger.info(
                '%s',
                truncate_with_ellipsis(
                    article.content,
                    _PREVIEW_LENGTH,
                ),
            )
            logger.info(_SEPARATOR)
    else:
        logger.error('Ошибка!')
        logger.error(
            '  %s', request.error_message,
        )

    if request.processing_time_ms:
        logger.info(
            'Время обработки: %.0f мс',
            request.processing_time_ms,
        )


def _parse_args() -> argparse.Namespace:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Тестирование paywall',
    )
    parser.add_argument(
        'url', help='URL статьи',
    )
    parser.add_argument(
        '--user-id',
        type=int,
        default=_DEFAULT_USER_ID,
        help='ID пользователя (для авторизации)',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Показать превью текста',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    asyncio.run(
        test_url(args.url, args.user_id, args.verbose),
    )
