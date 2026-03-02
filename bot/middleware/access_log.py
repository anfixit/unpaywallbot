"""Middleware для логирования действий пользователей.

Сохраняет структурированные логи в JSON-формате для последующего
анализа и обнаружения аномалий.
"""

import json
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.models.user_request import UserRequest

__all__ = ['AccessLogMiddleware']


class AccessLogMiddleware(BaseMiddleware):
    """Логирует все действия пользователей в JSON-файл."""

    def __init__(self, log_dir: Path = Path('data/logs')) -> None:
        """Инициализировать middleware.

        Args:
            log_dir: Директория для хранения логов.
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Текущий файл лога (по дням)
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        self.log_file = self.log_dir / f'access_{self.current_date}.jsonl'

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Обработать событие с логированием."""
        start_time = time.time()
        request_id = str(uuid4())[:8]

        # Базовая информация о запросе
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id,
            'event_type': event.__class__.__name__,
        }

        # Добавляем информацию о пользователе
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
            log_entry.update({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'language_code': user.language_code,
            })

        # Добавляем специфичную для события информацию
        if isinstance(event, Message):
            log_entry.update({
                'message_id': event.message_id,
                'chat_id': event.chat.id,
                'text': event.text[:500] if event.text else None,
                'has_url': 'http' in (event.text or ''),
            })

        if isinstance(event, CallbackQuery):
            log_entry.update({
                'callback_data': event.data,
                'message_id': event.message.message_id if event.message else None,
            })

        try:
            # Выполняем хендлер
            result = await handler(event, data)

            # Успех
            log_entry['status'] = 'success'
            log_entry['duration_ms'] = round((time.time() - start_time) * 1000, 2)

            # Если есть UserRequest в данных, добавляем информацию
            if 'request' in data and isinstance(data['request'], UserRequest):
                req = data['request']
                log_entry['paywall'] = {
                    'domain': req.paywall_info.domain if req.paywall_info else None,
                    'type': str(req.paywall_info.paywall_type) if req.paywall_info else None,
                    'method': str(req.paywall_info.suggested_method) if req.paywall_info else None,
                }
                if req.article:
                    log_entry['article'] = {
                        'title': req.article.title,
                        'content_length': len(req.article.content),
                    }

            return result

        except Exception as e:
            # Ошибка
            log_entry['status'] = 'error'
            log_entry['error'] = str(e)
            log_entry['duration_ms'] = round((time.time() - start_time) * 1000, 2)
            raise

        finally:
            # Сохраняем лог (в отдельном потоке, чтобы не блокировать)
            await self._save_log(log_entry)

    async def _save_log(self, entry: dict[str, Any]) -> None:
        """Сохранить запись в лог-файл."""
        # Проверяем, не сменился ли день
        today = datetime.now().strftime('%Y-%m-%d')
        if today != self.current_date:
            self.current_date = today
            self.log_file = self.log_dir / f'access_{today}.jsonl'

        # Записываем в файл (асинхронно через asyncio.to_thread)
        import asyncio
        await asyncio.to_thread(
            self._write_sync,
            entry,
        )

    def _write_sync(self, entry: dict[str, Any]) -> None:
        """Синхронная запись в файл."""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
