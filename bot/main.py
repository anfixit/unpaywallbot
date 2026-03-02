"""Точка входа в Telegram-бота.

Инициализирует все компоненты, подключает middleware
и хендлеры, запускает polling с корректной обработкой
сигналов завершения.
"""

import asyncio
import signal

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.handlers import callbacks, start, url_handler
from bot.middleware.access_log import AccessLogMiddleware
from bot.middleware.rate_limiter import RateLimiterMiddleware
from bot.middleware.whitelist import WhitelistMiddleware
from bot.storage.redis_client import redis_client
from bot.utils.logger import setup_logger

logger = setup_logger(__name__)


async def set_commands(bot: Bot) -> None:
    """Установить команды бота в интерфейсе Telegram."""
    commands = [
        BotCommand(
            command='start',
            description='Начать работу',
        ),
        BotCommand(
            command='help',
            description='Помощь',
        ),
    ]
    await bot.set_my_commands(commands)


async def shutdown() -> None:
    """Корректное завершение работы."""
    logger.info('Завершение работы...')
    await redis_client.close()
    logger.info('Redis соединение закрыто')


async def main() -> None:
    """Основная функция запуска бота.

    Pydantic Settings валидирует bot_token и encryption_key
    при создании синглтона settings (§3.4). Если переменные
    не заданы — ValidationError до вызова main().
    """
    logger.info(
        'Запуск бота в окружении: %s', settings.env,
    )

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
    )
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    # Middleware (порядок важен: whitelist → rate → log)
    dp.message.middleware(WhitelistMiddleware())
    dp.callback_query.middleware(WhitelistMiddleware())

    dp.message.middleware(RateLimiterMiddleware())
    dp.callback_query.middleware(RateLimiterMiddleware())

    dp.message.middleware(AccessLogMiddleware())
    dp.callback_query.middleware(AccessLogMiddleware())

    # Роутеры
    dp.include_router(start.router)
    dp.include_router(url_handler.router)
    dp.include_router(callbacks.router)

    await set_commands(bot)

    # Храним ссылку на задачу (§17.5)
    polling_task = asyncio.create_task(
        dp.start_polling(bot),
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(
                shutdown_polling(polling_task, dp, bot),
            ),
        )

    logger.info('Бот запущен и готов к работе')

    try:
        await polling_task
    except asyncio.CancelledError:
        logger.info('Polling отменён')
    finally:
        await shutdown()


async def shutdown_polling(
    polling_task: asyncio.Task,
    dp: Dispatcher,
    bot: Bot,
) -> None:
    """Остановить polling и завершить работу."""
    logger.info('Получен сигнал завершения...')
    polling_task.cancel()
    await dp.stop_polling()
    await bot.session.close()
    logger.info('Polling остановлен')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Бот остановлен пользователем')
    except Exception:
        logger.exception('Критическая ошибка')
