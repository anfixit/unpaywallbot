"""Callback-хендлеры для действий пользователя."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.url_handler import process_url_message

__all__ = ['router']

router = Router()


def _callback_message(
    callback: CallbackQuery,
) -> Message | None:
    """Вернуть обычное Message или None."""
    return (
        callback.message
        if isinstance(callback.message, Message)
        else None
    )


@router.callback_query(F.data == 'try_anyway')
async def try_anyway(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Попробовать доступные публичные источники."""
    message = _callback_message(callback)
    data = await state.get_data()
    url = data.get('url')

    if message is None or not isinstance(url, str):
        if message is not None:
            await message.answer(
                '❌ Сессия устарела. Отправь ссылку ещё раз.',
            )
        await callback.answer()
        return

    await callback.answer()
    await process_url_message(
        message=message,
        url=url,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        state=state,
    )


@router.callback_query(F.data == 'cancel')
async def cancel_action(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Отменить текущую операцию."""
    await state.clear()
    message = _callback_message(callback)
    if message is not None:
        await message.edit_text(
            '❌ Действие отменено. Отправь новую ссылку.',
        )
    await callback.answer()
