"""Хендлеры для команд /start и /help.

Показывают приветствие с inline-кнопками,
раскрывающими детали по запросу.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

__all__ = ['router']

router = Router()

# --- Тексты ---

_WELCOME = (
    '👋 *Привет!*\n\n'
    'Я исследовательский бот - показываю,'
    ' как устроены paywall-системы'
    ' новостных сайтов.\n\n'
    'Просто отправь мне ссылку на статью.'
)

_HELP = (
    '📖 *Как пользоваться*\n\n'
    '1. Скопируй ссылку на статью\n'
    '2. Отправь её мне\n'
    '3. Если нужна авторизация — я спрошу\n'
    '4. Получи полный текст\n\n'
    '*Не работает?*\n'
    '• Проверь, что ссылка ведёт на статью,'
    ' а не на главную\n'
    '• Попробуй другую статью\n'
    '• Подожди — некоторые методы требуют'
    ' времени'
)

_PUBLICATIONS = (
    '🌐 *Поддерживаемые издания*\n\n'
    '*Soft paywall:*\n'
    '• The Telegraph\n\n'
    '*Metered paywall:*\n'
    '• NY Times\n'
    '• New Yorker, Vanity Fair\n\n'
    '*Freemium:*\n'
    '• Spiegel (S+), Zeit (Z+),'
    ' FAZ (F+)\n'
    '• Süddeutsche\n\n'
    '*Hard paywall:*\n'
    '• Republic.io (нужен аккаунт)\n\n'
    '📦 Остальные — через archive.ph'
)

_ABOUT = (
    '📊 *О проекте*\n\n'
    'Исследование информационной'
    ' безопасности.\n\n'
    '*Цель:* показать, что клиентские'
    ' paywall (JS overlay) не являются'
    ' надёжной защитой контента,'
    ' и предложить рекомендации'
    ' по усилению.\n\n'
    '*Стек:* Python 3.12 · Aiogram 3'
    ' · Redis · Playwright\n\n'
    '⚠️ Бот создан исключительно'
    ' для исследовательских целей.\n\n'
    '👩‍💻 Автор: @Anfikus'
)

_SHAWARMA = (
    '🌯 *Спасибо за поддержку!*\n\n'
    'Шаверма — топливо для пет'
    ' проектов.\n\n'
    '💳 [Угостить автора]'
    '(https://messenger.online.sberbank.ru/sl/oc6Jc8tJawxKY6Q7H)'
)

# --- Клавиатуры ---


def _start_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура для /start."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text='📖 Помощь',
        callback_data='info_help',
    )
    builder.button(
        text='🌐 Издания',
        callback_data='info_pubs',
    )
    builder.button(
        text='📊 О проекте',
        callback_data='info_about',
    )
    builder.button(
        text='🌯 Шаверма автору',
        callback_data='info_shawarma',
    )
    builder.adjust(2, 2)
    return builder


def _back_keyboard() -> InlineKeyboardBuilder:
    """Кнопка «Назад» к главному меню."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text='🔙 Назад',
        callback_data='back_start',
    )
    return builder


# --- Хендлеры команд ---


@router.message(Command('start'))
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start."""
    await message.answer(
        _WELCOME,
        parse_mode='Markdown',
        reply_markup=(
            _start_keyboard().as_markup()
        ),
    )


@router.message(Command('help'))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help."""
    await message.answer(
        _HELP,
        parse_mode='Markdown',
        reply_markup=(
            _back_keyboard().as_markup()
        ),
    )


# --- Callback-хендлеры для кнопок ---

_INFO_MAP: dict[str, str] = {
    'info_help': _HELP,
    'info_pubs': _PUBLICATIONS,
    'info_about': _ABOUT,
    'info_shawarma': _SHAWARMA,
}


@router.callback_query(
    lambda c: c.data in _INFO_MAP,
)
async def info_callback(
    callback: CallbackQuery,
) -> None:
    """Показать информацию по кнопке."""
    text = _INFO_MAP[callback.data]
    await callback.message.edit_text(
        text,
        parse_mode='Markdown',
        reply_markup=(
            _back_keyboard().as_markup()
        ),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(
    lambda c: c.data == 'back_start',
)
async def back_to_start(
    callback: CallbackQuery,
) -> None:
    """Вернуться к главному меню."""
    await callback.message.edit_text(
        _WELCOME,
        parse_mode='Markdown',
        reply_markup=(
            _start_keyboard().as_markup()
        ),
    )
    await callback.answer()
