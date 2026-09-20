from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from db.base import AsyncSessionLocal
from db.repo import get_user_by_telegram_id


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session
            telegram_id = None
            if isinstance(event, Message):
                telegram_id = event.from_user.id if event.from_user else None
            elif isinstance(event, CallbackQuery):
                telegram_id = event.from_user.id if event.from_user else None

            if telegram_id:
                user = await get_user_by_telegram_id(session, telegram_id)
                data["current_user"] = user
            else:
                data["current_user"] = None

            return await handler(event, data)
