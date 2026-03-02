"""Middleware для логирования действий пользователей.

Сохраняет структурированные логи в JSON-формате
для последующего анализа и обнаружения аномалий.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    Message,
    TelegramObject,
)

from bot.models.user_request import UserRequest

__all__ = ['AccessLogMiddleware']


class AccessLogMiddleware(BaseMiddleware):
    """Логирует действия пользователей в JSON-файл."""

    def __init__(
        self,
        log_dir: Path = Path('data/logs'),
    ) -> None:
        """Инициализировать middleware.

        Args:
            log_dir: Директория для хранения логов.
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(UTC).strftime('%Y-%m-%d')
        self.current_date = today
        self.log_file = (
            self.log_dir / f'access_{today}.jsonl'
        )
        super().__init__()

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Обработать событие с логированием."""
        start_time = time.time()
        request_id = str(uuid4())[:8]

        log_entry: dict[str, Any] = {
            'timestamp': (
                datetime.now(UTC).isoformat()
            ),
            'request_id': request_id,
            'event_type': (
                event.__class__.__name__
            ),
        }

        if isinstance(
            event, (Message, CallbackQuery),
        ):
            user = event.from_user
            log_entry.update({
                'user_id': user.id,
                'username': user.username,
            })

        if isinstance(event, Message):
            log_entry.update({
                'message_id': event.message_id,
                'chat_id': event.chat.id,
                'has_url': (
                    'http' in (event.text or '')
                ),
            })

        if isinstance(event, CallbackQuery):
            log_entry.update({
                'callback_data': event.data,
                'message_id': (
                    event.message.message_id
                    if event.message else None
                ),
            })

        try:
            result = await handler(event, data)

            log_entry['status'] = 'success'
            log_entry['duration_ms'] = round(
                (time.time() - start_time) * 1000, 2,
            )

            self._enrich_from_request(
                log_entry, data,
            )
            return result

        except Exception:
            log_entry['status'] = 'error'
            log_entry['duration_ms'] = round(
                (time.time() - start_time) * 1000, 2,
            )
            raise

        finally:
            await self._save_log(log_entry)

    @staticmethod
    def _enrich_from_request(
        log_entry: dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        """Добавить данные из UserRequest."""
        req = data.get('request')
        if not isinstance(req, UserRequest):
            return

        if req.paywall_info:
            pi = req.paywall_info
            log_entry['paywall'] = {
                'domain': pi.domain,
                'type': str(pi.paywall_type),
                'method': (
                    str(pi.suggested_method)
                    if pi.suggested_method
                    else None
                ),
            }

        if req.article:
            log_entry['article'] = {
                'title': req.article.title,
                'content_length': (
                    len(req.article.content)
                ),
            }

    async def _save_log(
        self,
        entry: dict[str, Any],
    ) -> None:
        """Сохранить запись в лог-файл."""
        today = (
            datetime.now(UTC).strftime('%Y-%m-%d')
        )
        if today != self.current_date:
            self.current_date = today
            self.log_file = (
                self.log_dir
                / f'access_{today}.jsonl'
            )

        await asyncio.to_thread(
            self._write_sync, entry,
        )

    def _write_sync(
        self,
        entry: dict[str, Any],
    ) -> None:
        """Синхронная запись в файл."""
        with open(
            self.log_file,
            'a',
            encoding='utf-8',
        ) as f:
            f.write(
                json.dumps(
                    entry, ensure_ascii=False,
                )
                + '\n'
            )
