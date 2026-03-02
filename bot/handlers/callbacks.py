"""Хендлеры для inline-кнопок.

Обрабатывают ответы пользователя на вопросы бота
(авторизация, отмена, пагинация).
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.handlers.url_handler import (
    process_url_with_account,
)

__all__ = ['router']

router = Router()


async def _handle_auth_callback(
    callback: CallbackQuery,
    state: FSMContext,
    has_account: bool,
) -> None:
    """Общая логика для auth_yes и auth_no."""
    status = (
        '⏳ Пробую с авторизацией...'
        if has_account
        else '⏳ Пробую без авторизации...'
    )
    await callback.message.edit_text(status)

    data = await state.get_data()
    url = data.get('url')

    if not url:
        await callback.message.answer(
            '❌ Что-то пошло не так. '
            'Отправь ссылку ещё раз.',
        )
        await callback.answer()
        return

    await process_url_with_account(
        message=callback.message,
        url=url,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        has_account=has_account,
        state=state,
    )
    await callback.answer()


@router.callback_query(F.data == 'auth_yes')
async def auth_yes(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Пользователь подтвердил наличие аккаунта."""
    await _handle_auth_callback(
        callback, state, has_account=True,
    )


@router.callback_query(F.data == 'auth_no')
async def auth_no(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Пользователь сказал, что аккаунта нет."""
    await _handle_auth_callback(
        callback, state, has_account=False,
    )


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


@router.callback_query(F.data.startswith('page:'))
async def pagination(
    callback: CallbackQuery,
) -> None:
    """Обработка пагинации (заглушка)."""
    await callback.answer('Функция в разработке')
