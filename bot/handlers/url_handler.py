"""Основной хендлер для обработки URL.

Получает ссылку от пользователя, классифицирует paywall,
спрашивает про авторизацию если нужно, и запускает
оркестратор.
"""

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.text_formatter import split_into_chunks
from bot.utils.url_utils import is_valid_url, normalize_url

__all__ = ['router']

router = Router()

# Lazy init — не создаём Orchestrator при импорте,
# чтобы избежать side effects (§21.5).
_orchestrator = None


def _get_orchestrator():
    """Получить или создать синглтон оркестратора."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        from bot.services.orchestrator import (
            Orchestrator,
        )
        _orchestrator = Orchestrator()
    return _orchestrator


_URL_PATTERN = re.compile(r'https?://[^\s]+')


def extract_url(text: str) -> str | None:
    """Извлечь первый URL из текста сообщения."""
    match = _URL_PATTERN.search(text)
    return match.group(0) if match else None


async def process_url_with_account(
    message: Message,
    url: str,
    user_id: int,
    username: str | None,
    has_account: bool,
    state: FSMContext,
) -> None:
    """Обработать URL с известным наличием аккаунта."""
    await state.clear()

    status_msg = await message.answer(
        '🔍 Анализирую статью...',
    )

    orchestrator = _get_orchestrator()
    request = await orchestrator.process_url(
        url=url,
        user_id=user_id,
        username=username,
        skip_cache=False,
    )

    await status_msg.delete()

    if request.success and request.article:
        title = (
            request.article.title or 'Без заголовка'
        )
        await message.answer(
            f'📰 *{title}*\n\n'
            f'_{request.article.url}_',
            parse_mode='Markdown',
        )

        chunks = split_into_chunks(
            request.article.content,
        )
        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                header = (
                    f'*Часть {i}/{len(chunks)}*'
                )
                chunk = f'{header}\n\n{chunk}'
            await message.answer(
                chunk, parse_mode='Markdown',
            )
    else:
        error_text = (
            '❌ Не удалось получить статью.\n\n'
        )
        if request.error_message:
            error_text += (
                f'Ошибка: {request.error_message}'
            )
        else:
            error_text += (
                'Попробуй другую ссылку или '
                'проверь, доступна ли статья.'
            )
        await message.answer(error_text)


@router.message(F.text)
async def handle_message(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработать текстовое сообщение (URL)."""
    text = message.text.strip()
    url = extract_url(text)

    if not url:
        await message.answer(
            '❌ Не нашёл ссылку в сообщении.\n'
            'Отправь прямую ссылку на статью.',
        )
        return

    if not is_valid_url(url):
        await message.answer(
            '❌ Это не похоже на валидный URL.\n'
            'Убедись, что ссылка начинается '
            'с http:// или https://',
        )
        return

    normalized_url = normalize_url(url)
    await state.update_data(url=normalized_url)

    status_msg = await message.answer(
        '🔍 Анализирую статью...',
    )

    orchestrator = _get_orchestrator()
    paywall_info = (
        await orchestrator.classifier.classify(
            normalized_url,
        )
    )

    await status_msg.delete()

    if paywall_info.requires_auth:
        builder = InlineKeyboardBuilder()
        builder.button(
            text='✅ Да, есть',
            callback_data='auth_yes',
        )
        builder.button(
            text='❌ Нет аккаунта',
            callback_data='auth_no',
        )
        builder.button(
            text='🔙 Отмена',
            callback_data='cancel',
        )
        builder.adjust(2, 1)

        await message.answer(
            '🔒 Для доступа к '
            f'{paywall_info.domain}'
            ' нужна авторизация.\n'
            'Есть аккаунт на этом сайте?',
            reply_markup=builder.as_markup(),
        )
    else:
        await process_url_with_account(
            message=message,
            url=normalized_url,
            user_id=message.from_user.id,
            username=message.from_user.username,
            has_account=False,
            state=state,
        )
