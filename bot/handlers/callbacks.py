"""Хендлеры для inline-кнопок.

Обрабатывают ответы пользователя на вопросы бота.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.handlers.url_handler import process_url_with_account

router = Router()


@router.callback_query(F.data == 'auth_yes')
async def auth_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Пользователь сказал, что у него есть аккаунт."""
    await callback.message.edit_text('⏳ Пробую с авторизацией...')

    # Получаем сохранённый URL из состояния
    data = await state.get_data()
    url = data.get('url')

    if not url:
        await callback.message.answer('❌ Что-то пошло не так. Отправь ссылку ещё раз.')
        await callback.answer()
        return

    # Передаём управление основному обработчику
    await process_url_with_account(
        message=callback.message,
        url=url,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        has_account=True,
        state=state,
    )
    await callback.answer()


@router.callback_query(F.data == 'auth_no')
async def auth_no(callback: CallbackQuery, state: FSMContext) -> None:
    """Пользователь сказал, что у него нет аккаунта."""
    await callback.message.edit_text('⏳ Пробую без авторизации...')

    data = await state.get_data()
    url = data.get('url')

    if not url:
        await callback.message.answer('❌ Что-то пошло не так. Отправь ссылку ещё раз.')
        await callback.answer()
        return

    await process_url_with_account(
        message=callback.message,
        url=url,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        has_account=False,
        state=state,
    )
    await callback.answer()


@router.callback_query(F.data == 'cancel')
async def cancel_action(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена текущего действия."""
    await state.clear()
    await callback.message.edit_text('❌ Действие отменено. Отправь новую ссылку.')
    await callback.answer()


@router.callback_query(F.data.startswith('page:'))
async def pagination(callback: CallbackQuery) -> None:
    """Обработка пагинации (если будет использоваться)."""
    # Пока заглушка, можно будет реализовать позже
    await callback.answer('Функция в разработке')
