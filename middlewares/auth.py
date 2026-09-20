import logging
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from db.base import AsyncSessionLocal
from db.repo import get_user_by_telegram_id

logger = logging.getLogger(__name__)


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
            text = None
            if isinstance(event, Message):
                telegram_id = event.from_user.id if event.from_user else None
                text = event.text
            elif isinstance(event, CallbackQuery):
                telegram_id = event.from_user.id if event.from_user else None
                text = event.data

            if telegram_id:
                user = await get_user_by_telegram_id(session, telegram_id)
                data["current_user"] = user

                # FSM state
                state: FSMContext = data.get("state")
                fsm_state = await state.get_state() if state else None

                logger.warning(
                    f"[AUTH] tg_id={telegram_id} text={text!r} "
                    f"user={user.name if user else None} "
                    f"role={user.role.value if user else None} "
                    f"fsm_state={fsm_state}"
                )
            else:
                data["current_user"] = None

            return await handler(event, data)
