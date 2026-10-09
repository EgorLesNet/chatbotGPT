"""/connect CODE — attach this Telegram account to a website (PWA) profile so it receives chat notifications.

The code is created on the website (Profile -> Connect Telegram) and stored in tg_connect_codes.
Deep link from the website: https://t.me/<bot>?start=connect_<CODE>
"""
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()

CODE_RE = re.compile(r"^[A-Za-z0-9]{6,12}$")


async def _connect(message: Message, session: AsyncSession, raw_code: str) -> None:
    code = raw_code.strip().upper()
    if not CODE_RE.match(code):
        await message.answer("Неверный код. Скопируйте его на сайте: Профиль → Подключить Telegram.")
        return

    tg_id = message.from_user.id
    row = (await session.execute(
        text("select user_id from tg_connect_codes where code = :c and expires_at > :now"),
        {"c": code, "now": datetime.utcnow()},
    )).first()
    if not row:
        await message.answer("Код не найден или истёк. Создайте новый на сайте.")
        return
    user_id = row[0]

    taken = (await session.execute(
        text("select id from users where telegram_id = :t"), {"t": tg_id}
    )).scalar_one_or_none()
    if taken is not None and taken != user_id:
        await message.answer(
            "Этот Telegram уже привязан к другому профилю бота, поэтому подключить его к этому аккаунту нельзя.\n"
            "Если это ваш профиль в боте, привяжите его командой /link."
        )
        return

    await session.execute(
        text("update users set telegram_id = :t, notifications = true where id = :u"),
        {"t": tg_id, "u": user_id},
    )
    await session.execute(text("delete from tg_connect_codes where user_id = :u"), {"u": user_id})
    await session.commit()
    await message.answer("✅ Telegram подключён. Теперь сообщения из чатов объектов будут приходить сюда.")


@router.message(Command("connect"))
async def connect_command(message: Message, command: CommandObject, session: AsyncSession):
    if not command.args:
        await message.answer("Отправьте команду вида /connect КОД. Код берётся на сайте: Профиль → Подключить Telegram.")
        return
    await _connect(message, session, command.args)


@router.message(F.text.regexp(r"^/start(?:@\w+)?\s+connect_[A-Za-z0-9]{6,12}$"))
async def connect_deeplink(message: Message, session: AsyncSession):
    await _connect(message, session, message.text.split("connect_", 1)[1])
