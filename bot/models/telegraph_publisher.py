"""Публикация статей в Telegra.ph.

Длинные статьи (> MAX_MESSAGE_LENGTH) публикуются
в Telegraph и пользователю отправляется ссылка.
Telegram рендерит Instant View автоматически.

Зависимость: ``uv add 'telegraph[aio]'``
"""

import logging

from bot.constants import MAX_MESSAGE_LENGTH

__all__ = ['TelegraphPublisher']

logger = logging.getLogger(__name__)

# Порог: если текст длиннее — публикуем
# в Telegraph, иначе — в чат напрямую.
_TELEGRAPH_THRESHOLD = MAX_MESSAGE_LENGTH - 200


class TelegraphPublisher:
    """Ленивый синглтон для Telegraph API."""

    def __init__(self) -> None:
        self._token: str | None = None

    async def _ensure_account(self) -> None:
        """Создать аккаунт если нет токена."""
        if self._token:
            return

        from telegraph.aio import Telegraph

        client = Telegraph()
        account = await client.create_account(
            short_name='UnpaywallBot',
            author_name='Unpaywall Bot',
        )
        self._token = account['access_token']
        logger.info('Telegraph аккаунт создан')

    async def publish(
        self,
        title: str,
        text: str,
        author: str | None = None,
        source_url: str | None = None,
    ) -> str | None:
        """Опубликовать статью в Telegraph.

        Args:
            title: Заголовок статьи.
            text: Полный текст статьи.
            author: Автор.
            source_url: Ссылка на оригинал.

        Returns:
            URL страницы на telegra.ph
            или None при ошибке.
        """
        try:
            await self._ensure_account()

            from telegraph.aio import Telegraph

            client = Telegraph(self._token)

            # Конвертируем plain text → HTML
            html = _text_to_html(
                text, source_url,
            )

            response = await client.create_page(
                title=title[:256],
                html_content=html,
                author_name=author or 'Источник',
                author_url=source_url or '',
            )

            url = response.get('url', '')
            if url:
                logger.info(
                    'Опубликовано в Telegraph: %s',
                    url,
                )
            return url or None

        except Exception:
            logger.exception(
                'Ошибка публикации в Telegraph',
            )
            return None

    @staticmethod
    def should_use_telegraph(text: str) -> bool:
        """Нужна ли публикация в Telegraph.

        Args:
            text: Текст статьи.

        Returns:
            True если текст слишком длинный для
            одного сообщения Telegram.
        """
        return len(text) > _TELEGRAPH_THRESHOLD


def _text_to_html(
    text: str,
    source_url: str | None = None,
) -> str:
    """Конвертировать plain text в HTML.

    Абзацы (разделённые ``\\n\\n``) → ``<p>``.
    Одиночные ``\\n`` → ``<br>``.

    Args:
        text: Plain text.
        source_url: Ссылка на оригинал.

    Returns:
        HTML-строка.
    """
    paragraphs = text.split('\n\n')
    html_parts: list[str] = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Заменяем одиночные переносы на <br>
        para = para.replace('\n', '<br>')
        html_parts.append(f'<p>{para}</p>')

    if source_url:
        html_parts.append(
            f'<p><a href="{source_url}">'
            f'Оригинал статьи</a></p>',
        )

    return '\n'.join(html_parts)


# Lazy singleton (§21.5)
_publisher: TelegraphPublisher | None = None


def get_telegraph_publisher() -> TelegraphPublisher:
    """Получить синглтон TelegraphPublisher."""
    global _publisher  # noqa: PLW0603
    if _publisher is None:
        _publisher = TelegraphPublisher()
    return _publisher
