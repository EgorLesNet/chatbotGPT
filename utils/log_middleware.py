"""Aiogram middleware — логирует каждое входящее сообщение/callback пользователя."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from utils.logger import log_action


class UserActionMiddleware(BaseMiddleware):
    """Логирует каждое Message и CallbackQuery в db/logs/<user_id>.jsonl."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        action = "unknown"
        details: dict[str, Any] = {}

        if isinstance(event, Message):
            user = event.from_user
            if event.text:
                action = "message"
                details = {"text": event.text[:200]}
            elif event.voice:
                action = "voice_message"
                details = {"duration": event.voice.duration}
            elif event.document:
                action = "document"
                details = {"file_name": event.document.file_name}
            else:
                action = "message_other"

        elif isinstance(event, CallbackQuery):
            user = event.from_user
            action = "callback"
            details = {"data": event.data}

        if user:
            log_action(user.id, action, details)

        return await handler(event, data)
