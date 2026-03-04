"""Хендлеры для inline-кнопок.

Обрабатывают ответы пользователя на вопросы бота
(авторизация, отмена, пагинация).
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.handlers.url_handler import (
    process_url_message,
)

__all__ = ['router']

router = Router()


@router.callback_query(F.data == 'try_anyway')
async def try_anyway(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Пользователь хочет попробовать hard paywall."""
    data = await state.get_data()
    url = data.get('url')

    if not url:
        await callback.message.answer(
            '❌ Что-то пошло не так. '
            'Отправь ссылку ещё раз.',
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        '⏳ Пробую получить статью...',
    )

    await process_url_message(
        message=callback.message,
        url=url,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        state=state,
    )
    await callback.answer()


@router.callback_query(F.data == 'cancel')
async def cancel_action(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Отмена текущего действия."""
    await state.clear()
    await callback.message.edit_text(
        '❌ Действие отменено. '
        'Отправь новую ссылку.',
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith('page:'),
)
async def pagination(
    callback: CallbackQuery,
) -> None:
    """Обработка пагинации (заглушка)."""
    await callback.answer(
        'Функция в разработке',
    )
