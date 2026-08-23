"""Обработка пользовательских ссылок."""

import asyncio
import html
import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.constants import MAX_MESSAGE_LENGTH
from bot.models.telegraph_publisher import (
    TelegraphPublisher,
    get_telegraph_publisher,
)
from bot.services.orchestrator import Orchestrator
from bot.utils.request_context import set_current_request
from bot.utils.text_formatter import split_into_chunks
from bot.utils.url_utils import (
    extract_domain,
    is_valid_url,
    normalize_url,
)

__all__ = ['router']

logger = logging.getLogger(__name__)
router = Router()

_orchestrator: Orchestrator | None = None
_URL_PATTERN = re.compile(r'https?://[^\s]+')
_TRAILING_PUNCTUATION = '.,;:!?)]}'

# Длина префикса «📄 Часть i/N\n\n» с запасом
# на трёхзначные номера частей.
_PART_HEADER_RESERVE = 40


def _get_orchestrator() -> Orchestrator:
    """Получить или создать Orchestrator."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def _get_telegraph_publisher() -> TelegraphPublisher:
    """Получить издатель Telegraph."""
    return get_telegraph_publisher()


def extract_url(text: str) -> str | None:
    """Извлечь первый HTTP(S) URL из текста."""
    match = _URL_PATTERN.search(text)
    if not match:
        return None
    return match.group(0).rstrip(_TRAILING_PUNCTUATION)


async def _delete_status_message(message: Message) -> None:
    """Удалить служебное сообщение, если оно ещё существует."""
    try:
        await message.delete()
    except Exception:
        logger.debug(
            'Не удалось удалить status message',
            exc_info=True,
        )


async def process_url_message(
    message: Message,
    url: str,
    user_id: int,
    state: FSMContext,
) -> None:
    """Обработать URL и отправить результат."""
    await state.clear()
    status_msg = await message.answer(
        '🔍 Анализирую статью...',
    )
    domain = extract_domain(url)

    try:
        async with asyncio.timeout(
            settings.request_timeout_seconds,
        ):
            request = await _get_orchestrator().process_url(
                url=url,
                user_id=user_id,
                skip_cache=False,
            )
    except TimeoutError:
        logger.warning(
            'Таймаут обработки домена: %s',
            domain,
        )
        await message.answer(
            '⏳ Сайт отвечал слишком долго. '
            'Попробуй повторить позже.',
        )
        return
    except Exception:
        logger.exception(
            'Ошибка обработки домена: %s',
            domain,
        )
        await message.answer(
            '❌ Не удалось обработать ссылку '
            'из-за внутренней ошибки.',
        )
        return
    finally:
        await _delete_status_message(status_msg)

    # Метаданные обработки для access log.
    set_current_request(request)

    if not request.success or not request.article:
        await message.answer(
            '❌ Не удалось извлечь доступный текст статьи.\n\n'
            'Сайт мог заблокировать запрос, изменить разметку '
            'или не отдавать содержимое без авторизации.',
        )
        return

    article = request.article
    title = article.title or 'Без заголовка'
    source_url = html.escape(article.url, quote=True)

    header_parts = [
        f'📰 <b>{html.escape(title)}</b>',
    ]
    if article.author:
        header_parts.append(
            f'✍️ {html.escape(article.author)}',
        )
    header_parts.append(
        f'🔗 <a href="{source_url}">Источник</a>',
    )
    header = '\n'.join(header_parts)

    publisher = (
        _get_telegraph_publisher()
        if settings.telegraph_enabled
        else None
    )
    if (
        publisher is not None
        and publisher.should_use_telegraph(
            article.content,
        )
    ):
        telegraph_url = await publisher.publish(
            title=title,
            text=article.content,
            author=article.author,
            source_url=article.url,
        )
        if telegraph_url:
            safe_telegraph_url = html.escape(
                telegraph_url,
                quote=True,
            )
            await message.answer(
                f'{header}\n\n'
                f'📖 <a href="{safe_telegraph_url}">'
                'Открыть извлечённый текст</a>',
                parse_mode='HTML',
                disable_web_page_preview=False,
            )
            return

    await message.answer(
        header,
        parse_mode='HTML',
        disable_web_page_preview=True,
    )

    # Резерв под заголовок «Часть i/N»: с ним
    # сообщение не должно превышать лимит Telegram.
    chunks = split_into_chunks(
        article.content,
        MAX_MESSAGE_LENGTH - _PART_HEADER_RESERVE,
    )
    for index, chunk in enumerate(chunks, 1):
        text = chunk
        if len(chunks) > 1:
            text = (
                f'📄 Часть {index}/{len(chunks)}'
                f'\n\n{chunk}'
            )
        await message.answer(text)


@router.message(F.text)
async def handle_message(
    message: Message,
    state: FSMContext,
) -> None:
    """Проверить сообщение и запустить обработку URL."""
    text = (message.text or '').strip()
    url = extract_url(text)

    if not url:
        await message.answer(
            '❌ Не нашёл ссылку в сообщении.\n'
            'Отправь прямую HTTP(S)-ссылку на статью.',
        )
        return

    if not is_valid_url(url):
        await message.answer(
            '❌ Ссылка небезопасна или имеет '
            'неподдерживаемый формат.',
        )
        return

    normalized_url = normalize_url(url)
    await state.update_data(url=normalized_url)

    user = message.from_user
    if user is None:
        await message.answer(
            '❌ Не удалось определить пользователя.',
        )
        return

    orchestrator = _get_orchestrator()
    paywall_info = await orchestrator.classifier.classify(
        normalized_url,
    )

    if paywall_info.requires_auth:
        builder = InlineKeyboardBuilder()
        builder.button(
            text='🔓 Попробовать доступные способы',
            callback_data='try_anyway',
        )
        builder.button(
            text='🔙 Отмена',
            callback_data='cancel',
        )
        builder.adjust(1)

        await message.answer(
            f'🔒 <b>{html.escape(paywall_info.domain)}</b> '
            'не отдаёт полный текст без авторизации.\n\n'
            'Бот попробует только доступные публичные '
            'источники и архивные снимки.',
            parse_mode='HTML',
            reply_markup=builder.as_markup(),
        )
        return

    await process_url_message(
        message=message,
        url=normalized_url,
        user_id=user.id,
        state=state,
    )
