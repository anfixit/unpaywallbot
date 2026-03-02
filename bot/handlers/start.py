"""Хендлеры для команд /start и /help.

Показывают приветствие, информацию о боте
и краткую инструкцию.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

__all__ = ['router']

router = Router()


@router.message(Command('start'))
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start."""
    text = (
        '👋 *Привет! Я бот для исследования'
        ' paywall-систем.*\n\n'
        'Я умею обходить платный доступ на разных'
        ' новостных сайтах в рамках дипломного'
        ' исследования.\n\n'
        '📩 *Как пользоваться:*\n'
        'Просто отправь мне ссылку на статью,'
        ' и я попробую достать полный текст.\n\n'
        '🌐 *Поддерживаемые издания:*\n'
        '• The Telegraph (soft paywall)\n'
        '• NY Times (metered paywall)\n'
        '• Spiegel, Zeit, FAZ,'
        ' Süddeutsche (freemium)\n'
        '• New Yorker, Vanity Fair\n'
        '• Republic.io (hard paywall'
        ' — требуется аккаунт)\n'
        '• И другие через archive.ph\n\n'
        '⚠️ *Важно:* Бот создан только'
        ' для образовательных целей.'
    )
    await message.answer(
        text, parse_mode='Markdown',
    )


@router.message(Command('help'))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help."""
    text = (
        '🆘 *Помощь по использованию*\n\n'
        '*Как получить статью:*\n'
        '1. Найди ссылку на статью на одном'
        ' из поддерживаемых сайтов\n'
        '2. Отправь её мне\n'
        '3. Если сайт требует авторизацию,'
        ' я спрошу, есть ли у тебя аккаунт\n'
        '4. Получи полный текст статьи\n\n'
        '*Что делать, если не работает:*\n'
        '• Проверь, что ссылка ведёт на статью,'
        ' а не на главную страницу\n'
        '• Попробуй другую статью\n'
        '• Подожди немного — некоторые методы'
        ' требуют времени\n\n'
        '*О проекте:*\n'
        'Дипломная работа по информационной'
        ' безопасности.\n'
        'Исследование уязвимостей клиентских'
        ' paywall-систем.'
    )
    await message.answer(
        text, parse_mode='Markdown',
    )
