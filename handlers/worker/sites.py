from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import get_sites_for_worker, get_site_by_id, get_site_by_invite_code, is_member, add_member, get_user_by_telegram_id
from keyboards.worker import kb_worker_main, kb_sites_inline
from locales.i18n import t

router = Router()

ALL_WORKER_SITES_BTN = [t("btn_worker_sites", l) for l in ("ru", "en", "tg", "uz")]


@router.message(F.text.in_(ALL_WORKER_SITES_BTN))
async def worker_sites(message: Message, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.worker:
        return
    sites = await get_sites_for_worker(session, current_user.id)
    if not sites:
        await message.answer(t("no_sites_worker", lang), reply_markup=kb_worker_main(lang))
        return
    await message.answer(t("your_sites", lang), reply_markup=kb_sites_inline(sites, action="w_site"))


@router.callback_query(F.data.startswith("w_site:"))
async def worker_site_detail(callback: CallbackQuery, session: AsyncSession, lang: str):
    site_id = int(callback.data.split(":")[1])
    site = await get_site_by_id(session, site_id)
    if not site:
        await callback.answer(t("site_not_found", lang), show_alert=True)
        return
    workers_list = ", ".join(m.worker.name for m in site.members) or t("no_workers", lang)
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={site.invite_code}"
    await callback.message.edit_text(
        t("site_detail", lang, name=site.name, address=site.address, workers=workers_list, link=link)
    )
    await callback.answer()
