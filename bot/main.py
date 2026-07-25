"""Точка входа Telegram-бота."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.handlers import callbacks, start, url_handler
from bot.middleware.access_log import AccessLogMiddleware
from bot.middleware.rate_limiter import RateLimiterMiddleware
from bot.middleware.whitelist import WhitelistMiddleware
from bot.storage.redis_client import get_redis_client
from bot.utils.logger import setup_logger, shutdown_logging

logger = setup_logger(__name__)


async def set_commands(bot: Bot) -> None:
    """Установить команды Telegram."""
    await bot.set_my_commands([
        BotCommand(
            command='start',
            description='Начать работу',
        ),
        BotCommand(
            command='help',
            description='Помощь',
        ),
    ])


def build_dispatcher(storage: RedisStorage) -> Dispatcher:
    """Собрать Dispatcher без сетевых операций."""
    dp = Dispatcher(storage=storage)

    dp.message.middleware(WhitelistMiddleware())
    dp.callback_query.middleware(WhitelistMiddleware())
    dp.message.middleware(RateLimiterMiddleware())
    dp.callback_query.middleware(RateLimiterMiddleware())
    dp.message.middleware(AccessLogMiddleware())
    dp.callback_query.middleware(AccessLogMiddleware())

    dp.include_router(start.router)
    dp.include_router(url_handler.router)
    dp.include_router(callbacks.router)
    return dp


async def shutdown(
    *,
    storage: RedisStorage | None = None,
    bot: Bot | None = None,
) -> None:
    """Закрыть все открытые ресурсы приложения."""
    logger.info('Завершение работы...')

    if storage is not None:
        try:
            await storage.close()
        except Exception:
            logger.exception('Не удалось закрыть FSM storage')

    if bot is not None:
        try:
            await bot.session.close()
        except Exception:
            logger.exception('Не удалось закрыть Telegram session')

    try:
        await get_redis_client().close()
    except Exception:
        logger.exception('Не удалось закрыть Redis')

    shutdown_logging()


async def shutdown_polling(
    polling_task: asyncio.Task[object],
    dp: Dispatcher,
    bot: Bot,
) -> None:
    """Совместимый helper остановки polling для тестов."""
    polling_task.cancel()
    try:
        await dp.stop_polling()
    except RuntimeError:
        logger.debug('Polling уже остановлен')
    await bot.session.close()


async def main() -> None:
    """Подключить зависимости и запустить long polling."""
    logger.info(
        'Запуск бота в окружении: %s',
        settings.env,
    )

    redis = get_redis_client()
    await redis.connect()

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
    )
    storage = RedisStorage.from_url(settings.redis_url)
    dp = build_dispatcher(storage)

    try:
        await set_commands(bot)
        logger.info('Бот запущен и готов к работе')
        await dp.start_polling(
            bot,
            handle_signals=True,
            close_bot_session=False,
        )
    finally:
        await shutdown(storage=storage, bot=bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
