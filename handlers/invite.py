from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db.repo import get_site_by_invite_code, is_member, add_member, get_sites_for_worker
from db.models import UserRole, User
from sqlalchemy import select
from locales.i18n import t
from keyboards.worker import kb_worker_main

router = Router()


@router.message(F.text.startswith("/start "))
async def handle_invite(message: Message, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.worker:
        return
    code = message.text.split(" ", 1)[1].strip()
    site = await get_site_by_invite_code(session, code)
    if not site:
        await message.answer(t("invalid_invite", lang))
        return
    if await is_member(session, site.id, current_user.id):
        await message.answer(t("already_member", lang, name=site.name))
        return
    await add_member(session, site.id, current_user.id)
    await message.answer(t("joined_site", lang, name=site.name), reply_markup=kb_worker_main(lang))
    foreman_res = await session.execute(select(User).where(User.id == site.foreman_id))
    foreman = foreman_res.scalar_one_or_none()
    if foreman:
        f_lang = foreman.lang or "ru"
        try:
            await message.bot.send_message(
                foreman.telegram_id,
                t("worker_joined_notify", f_lang, worker=current_user.name, site=site.name)
            )
        except Exception:
            pass
