from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from db.models import UserRole
from db.repo import get_sites_by_foreman, create_site, get_site_by_id
from keyboards.foreman import kb_foreman_main, kb_sites_inline
from keyboards.common import kb_remove
from locales.i18n import t

router = Router()
BOT_USERNAME = None


class SiteCreateState(StatesGroup):
    name = State()
    address = State()


ALL_MY_SITES = [t("btn_my_sites", l) for l in ("ru", "en", "tg", "uz")]
ALL_CREATE_SITE = [t("btn_create_site", l) for l in ("ru", "en", "tg", "uz")]


@router.message(F.text.in_(ALL_MY_SITES))
async def foreman_my_sites(message: Message, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.foreman:
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer(t("no_sites_foreman", lang), reply_markup=kb_foreman_main(lang))
        return
    await message.answer(t("your_sites", lang), reply_markup=kb_sites_inline(sites, action="f_site"))


@router.callback_query(F.data.startswith("f_site:"))
async def foreman_site_detail(callback: CallbackQuery, session: AsyncSession, lang: str):
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


@router.message(F.text.in_(ALL_CREATE_SITE))
async def foreman_create_site_start(message: Message, state: FSMContext, current_user, lang: str):
    if not current_user or current_user.role != UserRole.foreman:
        return
    await message.answer(t("enter_site_name", lang), reply_markup=kb_remove())
    await state.set_state(SiteCreateState.name)


@router.message(SiteCreateState.name)
async def foreman_site_name(message: Message, state: FSMContext, lang: str):
    await state.update_data(name=message.text.strip())
    await message.answer(t("enter_site_address", lang))
    await state.set_state(SiteCreateState.address)


@router.message(SiteCreateState.address)
async def foreman_site_address(message: Message, state: FSMContext, session: AsyncSession, current_user, lang: str):
    data = await state.get_data()
    await state.clear()
    invite_code = uuid.uuid4().hex[:12]
    site = await create_site(session, data["name"], message.text.strip(), current_user.id, invite_code)
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={site.invite_code}"
    await message.answer(t("site_created", lang, name=site.name, link=link), reply_markup=kb_foreman_main(lang))
