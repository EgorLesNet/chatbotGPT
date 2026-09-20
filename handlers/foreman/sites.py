from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import create_site, get_sites_by_foreman, get_site_by_id
from keyboards.foreman import kb_foreman_main, kb_sites_inline, kb_site_actions
from keyboards.common import kb_remove
from utils.invite import generate_invite_code, make_invite_link

router = Router()


class NewSiteState(StatesGroup):
    name = State()
    address = State()


def _foreman_only(user) -> bool:
    return user and user.role == UserRole.foreman


@router.message(F.text == "🏗 Мои объекты")
async def my_sites(message: Message, session: AsyncSession, current_user):
    if not _foreman_only(current_user):
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer("У вас пока нет объектов. Создайте первый!", reply_markup=kb_foreman_main())
        return
    await message.answer("Ваши объекты:", reply_markup=kb_sites_inline(sites, action="f_site"))


@router.message(F.text == "➕ Новый объект")
async def new_site_start(message: Message, state: FSMContext, current_user):
    if not _foreman_only(current_user):
        return
    await message.answer("Введите название объекта:", reply_markup=kb_remove())
    await state.set_state(NewSiteState.name)


@router.message(NewSiteState.name)
async def new_site_name(message: Message, state: FSMContext):
    await state.update_data(name=(message.text or "").strip())
    await message.answer("Введите адрес объекта:")
    await state.set_state(NewSiteState.address)


@router.message(NewSiteState.address)
async def new_site_address(message: Message, state: FSMContext, session: AsyncSession, current_user):
    data = await state.get_data()
    await state.clear()
    invite_code = generate_invite_code()
    site = await create_site(session, data["name"], (message.text or "").strip(), current_user.id, invite_code)
    bot_info = await message.bot.get_me()
    link = make_invite_link(bot_info.username, invite_code)
    await message.answer(
        f"✅ Объект <b>{site.name}</b> создан!\n\n"
        f"📍 Адрес: {site.address}\n"
        f"🔗 Инвайт-ссылка для рабочих:\n<code>{link}</code>\n\n"
        f"Отправьте эту ссылку рабочим — при переходе они автоматически добавятся к объекту.",
        reply_markup=kb_foreman_main(),
    )


@router.callback_query(F.data.startswith("f_site:"))
async def site_detail(callback: CallbackQuery, session: AsyncSession, current_user):
    site_id = int(callback.data.split(":")[1])
    site = await get_site_by_id(session, site_id)
    if not site or site.foreman_id != current_user.id:
        await callback.answer("Объект не найден.", show_alert=True)
        return
    members_count = len(site.members)
    await callback.message.edit_text(
        f"🏗 <b>{site.name}</b>\n📍 {site.address}\n👷 Рабочих: {members_count}",
        reply_markup=kb_site_actions(site_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("f_invite:"))
async def show_invite(callback: CallbackQuery, session: AsyncSession, current_user):
    site_id = int(callback.data.split(":")[1])
    site = await get_site_by_id(session, site_id)
    if not site or site.foreman_id != current_user.id:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    bot_info = await callback.bot.get_me()
    link = make_invite_link(bot_info.username, site.invite_code)
    await callback.message.answer(
        f"🔗 Инвайт-ссылка для объекта <b>{site.name}</b>:\n<code>{link}</code>\n\n"
        "Отправьте ссылку рабочему — при переходе он автоматически добавится к объекту."
    )
    await callback.answer()
