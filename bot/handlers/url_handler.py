"""Основной хендлер для обработки URL.

Получает ссылку от пользователя, классифицирует
paywall и запускает оркестратор. Вопрос про аккаунт
задаётся только если headless_auth реально доступен.
"""

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.text_formatter import split_into_chunks
from bot.utils.url_utils import (
    is_valid_url,
    normalize_url,
)

__all__ = ['router']

router = Router()

# Lazy init — не создаём Orchestrator при импорте
# модуля, чтобы избежать side effects (§21.5).
_orchestrator = None


def _get_orchestrator():
    """Получить или создать синглтон."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        from bot.services.orchestrator import (
            Orchestrator,
        )
        _orchestrator = Orchestrator()
    return _orchestrator


_URL_PATTERN = re.compile(r'https?://[^\s]+')


def _get_telegraph_publisher():
    """Lazy import telegraph publisher.

    Returns None если модуль или зависимость
    ``telegraph`` не установлены.
    """
    try:
        from bot.services.telegraph_publisher import (
            get_telegraph_publisher,
        )
        return get_telegraph_publisher()
    except (ImportError, ModuleNotFoundError):
        return None

def extract_url(text: str) -> str | None:
    """Извлечь первый URL из текста."""
    match = _URL_PATTERN.search(text)
    return match.group(0) if match else None


async def process_url_message(
    message: Message,
    url: str,
    user_id: int,
    username: str | None,
    state: FSMContext,
) -> None:
    """Обработать URL и отправить результат.

    Args:
        message: Сообщение Telegram.
        url: Нормализованный URL.
        user_id: Telegram user_id.
        username: Telegram username.
        state: FSM-контекст.
    """
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
        article = request.article
        title = article.title or 'Без заголовка'

        # Заголовок + метаинформация
        header = f'📰 *{_escape_md(title)}*'
        if article.author:
            header += (
                f'\n✍️ {_escape_md(article.author)}'
            )
        header += f'\n🔗 {article.url}'

        publisher = _get_telegraph_publisher()

        if publisher and publisher.should_use_telegraph(
            article.content,
        ):
            # Длинная статья → Telegraph
            telegraph_url = await publisher.publish(
                title=title,
                text=article.content,
                author=article.author,
                source_url=article.url,
            )
            if telegraph_url:
                await message.answer(
                    f'{header}'
                    f'\n\n📖 Полный текст: '
                    f'{telegraph_url}',
                    parse_mode='Markdown',
                    disable_web_page_preview=False,
                )
                return

        # Короткая статья или Telegraph упал
        await message.answer(
            header,
            parse_mode='Markdown',
            disable_web_page_preview=True,
        )

        # Текст статьи по частям
        chunks = split_into_chunks(
            article.content,
        )
        for i, chunk in enumerate(chunks, 1):
            text = chunk
            if len(chunks) > 1:
                text = (
                    f'📄 *Часть {i}/{len(chunks)}*'
                    f'\n\n{chunk}'
                )
            await message.answer(text)
    else:
        error_text = (
            '❌ Не удалось получить статью.\n\n'
        )
        if request.error_message:
            error_text += (
                f'Причина: {request.error_message}'
            )
        else:
            error_text += (
                'Возможные причины:\n'
                '• Сайт блокирует серверные '
                'запросы\n'
                '• Статья за жёстким paywall\n'
                '• Страница не содержит текста\n\n'
                'Попробуй другую статью '
                'или другое издание.'
            )
        await message.answer(error_text)


def _escape_md(text: str) -> str:
    """Экранировать спецсимволы Markdown v1.

    Args:
        text: Исходный текст.

    Returns:
        Экранированный текст.
    """
    for char in ('_', '*', '[', ']', '`'):
        text = text.replace(char, f'\\{char}')
    return text


@router.message(F.text)
async def handle_message(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработать текстовое сообщение (URL).

    Flow:
    1. Извлечь URL из текста
    2. Классифицировать paywall
    3. Если requires_auth — спросить про аккаунт
       (информационно, т.к. headless пока не
       подключён)
    4. Запустить обработку
    """
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

    # Классификация для информирования
    orchestrator = _get_orchestrator()
    paywall_info = (
        await orchestrator.classifier.classify(
            normalized_url,
        )
    )

    if paywall_info.requires_auth:
        # Сообщаем что это hard paywall,
        # но обрабатываем в любом случае —
        # через archive.ph fallback
        builder = InlineKeyboardBuilder()
        builder.button(
            text='🔓 Попробовать всё равно',
            callback_data='try_anyway',
        )
        builder.button(
            text='🔙 Отмена',
            callback_data='cancel',
        )
        builder.adjust(1)

        await message.answer(
            f'🔒 *{paywall_info.domain}* '
            'использует жёсткий paywall.\n\n'
            'Полный текст может быть '
            'недоступен, но я попробую '
            'найти его через архив.',
            parse_mode='Markdown',
            reply_markup=builder.as_markup(),
        )
    else:
        await process_url_message(
            message=message,
            url=normalized_url,
            user_id=message.from_user.id,
            username=message.from_user.username,
            state=state,
        )
