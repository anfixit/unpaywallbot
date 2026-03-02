"""Основной хендлер для обработки URL.

Получает ссылку от пользователя, классифицирует paywall,
спрашивает про авторизацию если нужно, и запускает оркестратор.
"""

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.orchestrator import Orchestrator
from bot.utils.text_formatter import split_into_chunks
from bot.utils.url_utils import is_valid_url, normalize_url

router = Router()
orchestrator = Orchestrator()


def extract_url(text: str) -> str | None:
    """Извлечь URL из текста сообщения."""
    # Простой regex для поиска URL
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, text)
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
    # Очищаем состояние
    await state.clear()

    # Отправляем статус
    status_msg = await message.answer('🔍 Анализирую статью...')

    # Запускаем оркестратор
    request = await orchestrator.process_url(
        url=url,
        user_id=user_id,
        username=username,
        skip_cache=False,
    )

    await status_msg.delete()

    if request.success and request.article:
        # Успех — отправляем статью
        title = request.article.title or 'Без заголовка'
        await message.answer(
            f'📰 *{title}*\n\n'
            f'_{request.article.url}_',
            parse_mode='Markdown',
        )

        # Разбиваем текст на части
        chunks = split_into_chunks(request.article.content)
        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                chunk = f'*Часть {i}/{len(chunks)}*\n\n{chunk}'
            await message.answer(chunk, parse_mode='Markdown')
    else:
        # Ошибка
        error_text = '❌ Не удалось получить статью.\n\n'
        if request.error_message:
            error_text += f'Ошибка: {request.error_message}'
        else:
            error_text += 'Попробуй другую ссылку или проверь, доступна ли статья.'

        await message.answer(error_text)


@router.message(F.text)
async def handle_message(message: Message, state: FSMContext) -> None:
    """Обработать текстовое сообщение (ожидаем URL)."""
    text = message.text.strip()
    url = extract_url(text)

    if not url:
        await message.answer(
            '❌ Я не нашёл ссылку в твоём сообщении.\n'
            'Отправь мне прямую ссылку на статью.'
        )
        return

    # Проверяем валидность URL
    if not is_valid_url(url):
        await message.answer(
            '❌ Это не похоже на валидный URL.\n'
            'Убедись, что ссылка начинается с http:// или https://'
        )
        return

    # Нормализуем URL
    normalized_url = normalize_url(url)

    # Сохраняем в состояние
    await state.update_data(url=normalized_url)

    # Отправляем статус
    status_msg = await message.answer('🔍 Анализирую статью...')

    # Быстрая классификация для проверки, нужна ли авторизация
    paywall_info = await orchestrator.classifier.classify(normalized_url)

    await status_msg.delete()

    if paywall_info.requires_auth:
        # Спрашиваем про аккаунт
        builder = InlineKeyboardBuilder()
        builder.button(text='✅ Да, есть', callback_data='auth_yes')
        builder.button(text='❌ Нет аккаунта', callback_data='auth_no')
        builder.button(text='🔙 Отмена', callback_data='cancel')
        builder.adjust(2, 1)

        await message.answer(
            f'🔒 Для доступа к {paywall_info.domain} нужна авторизация.\n'
            'У тебя есть аккаунт на этом сайте?',
            reply_markup=builder.as_markup(),
        )
    else:
        # Не требует авторизации — пробуем сразу
        await process_url_with_account(
            message=message,
            url=normalized_url,
            user_id=message.from_user.id,
            username=message.from_user.username,
            has_account=False,
            state=state,
        )
