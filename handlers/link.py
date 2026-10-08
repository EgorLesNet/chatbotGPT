"""/link — issue a one-time code that links this Telegram profile to a PWA account."""
import secrets
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import WEB_APP_URL

router = Router()

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TTL_MINUTES = 15


@router.message(Command("link"))
async def link_command(message: Message, session: AsyncSession, current_user):
    if not current_user:
        await message.answer("Сначала зарегистрируйтесь в боте: /start")
        return

    linked = (await session.execute(
        text("select auth_id from users where id = :id"), {"id": current_user.id}
    )).scalar_one_or_none()
    if linked:
        await message.answer("✅ Этот профиль уже привязан к аккаунту на сайте.")
        return

    now = datetime.utcnow()
    await session.execute(
        text("delete from link_codes where user_id = :id or expires_at < :now"),
        {"id": current_user.id, "now": now},
    )
    code = "".join(secrets.choice(ALPHABET) for _ in range(8))
    await session.execute(
        text("insert into link_codes (code, user_id, expires_at, used) values (:c, :u, :e, false)"),
        {"c": code, "u": current_user.id, "e": now + timedelta(minutes=TTL_MINUTES)},
    )
    await session.commit()

    where = f"{WEB_APP_URL}/onboarding" if WEB_APP_URL else "странице привязки на сайте"
    await message.answer(
        f"🔗 Код привязки: <code>{code}</code>\n\n"
        f"Откройте {where}, войдите по email и введите код.\n"
        f"Код действует {TTL_MINUTES} минут и работает один раз. Никому его не передавайте."
    )
