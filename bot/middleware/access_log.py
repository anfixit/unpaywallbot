"""Privacy-aware structured access logging."""

import asyncio
import json
import os
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

from bot.config import settings
from bot.models.user_request import UserRequest
from bot.utils.privacy import pseudonymize_user_id
from bot.utils.request_context import (
    clear_current_request,
    get_current_request,
)

__all__ = ['AccessLogMiddleware']


class AccessLogMiddleware(BaseMiddleware):
    """Write JSONL logs without raw user identifiers by default."""

    def __init__(
        self,
        log_dir: Path = Path('data/logs'),
    ) -> None:
        """Initialize log storage."""
        self.log_dir = log_dir
        self.log_dir.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )
        self.log_dir.chmod(0o700)

        self.current_date = (
            datetime.now(UTC).strftime('%Y-%m-%d')
        )
        self.log_file = self._path_for_date(
            self.current_date,
        )
        self._write_lock = asyncio.Lock()
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
        """Process an update and persist an audit record."""
        start_time = time.monotonic()
        log_entry: dict[str, Any] = {
            'timestamp': datetime.now(UTC).isoformat(),
            'request_id': str(uuid4())[:8],
            'event_type': event.__class__.__name__,
        }

        user = getattr(event, 'from_user', None)
        if user is not None:
            if settings.log_user_identifiers:
                log_entry['user_id'] = user.id
                log_entry['username'] = user.username
            else:
                log_entry['user_hash'] = (
                    pseudonymize_user_id(user.id)
                )

        if isinstance(event, Message):
            log_entry.update({
                'message_id': event.message_id,
                'has_url': 'http' in (event.text or ''),
            })
            if settings.log_user_identifiers:
                log_entry['chat_id'] = event.chat.id

        if isinstance(event, CallbackQuery):
            log_entry.update({
                'callback_data': event.data,
                'message_id': (
                    event.message.message_id
                    if event.message else None
                ),
            })

        clear_current_request()

        try:
            result = await handler(event, data)
        except Exception:
            log_entry['status'] = 'error'
            raise
        else:
            log_entry['status'] = 'success'
            self._enrich_from_request(log_entry)
            return result
        finally:
            log_entry['duration_ms'] = round(
                (time.monotonic() - start_time) * 1000,
                2,
            )
            await self._save_log(log_entry)

    @staticmethod
    def _enrich_from_request(
        log_entry: dict[str, Any],
    ) -> None:
        """Add non-sensitive processing metadata."""
        request = get_current_request()
        if not isinstance(request, UserRequest):
            return

        if request.paywall_info:
            info = request.paywall_info
            log_entry['paywall'] = {
                'domain': info.domain,
                'type': str(info.paywall_type),
                'method': (
                    str(info.suggested_method)
                    if info.suggested_method
                    else None
                ),
            }

        if request.article:
            log_entry['article'] = {
                'content_length': len(
                    request.article.content,
                ),
            }

    def _path_for_date(self, date: str) -> Path:
        """Build a daily JSONL path."""
        return self.log_dir / f'access_{date}.jsonl'

    async def _save_log(
        self,
        entry: dict[str, Any],
    ) -> None:
        """Serialize writes to prevent interleaved JSON lines."""
        async with self._write_lock:
            today = datetime.now(UTC).strftime('%Y-%m-%d')
            if today != self.current_date:
                self.current_date = today
                self.log_file = self._path_for_date(today)

            await asyncio.to_thread(
                self._write_sync,
                entry,
            )

    def _write_sync(
        self,
        entry: dict[str, Any],
    ) -> None:
        """Append one record with mode 0600."""
        descriptor = os.open(
            self.log_file,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        with os.fdopen(
            descriptor,
            'a',
            encoding='utf-8',
        ) as file:
            file.write(
                json.dumps(
                    entry,
                    ensure_ascii=False,
                )
                + '\n',
            )
        self.log_file.chmod(0o600)
