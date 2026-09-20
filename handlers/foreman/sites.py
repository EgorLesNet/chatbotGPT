from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import get_sites_by_foreman, create_site
from filters.role import RoleFilter
from keyboards.foreman import kb_foreman_main, kb_sites_inline
from keyboards.common import kb_remove
from utils.invite import generate_invite_code

router = Router()
router.message.filter(RoleFilter(UserRole.foreman))
router.callback_query.filter(RoleFilter(UserRole.foreman))


class SiteCreateState(StatesGroup):
    name = State()
    address = State()


@router.message(F.text == "🏗 Мои объекты")
async def foreman_my_sites(message: Message, session: AsyncSession, current_user):
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer("У вас пока нет объектов. Нажмите ‘➕ Создать объект’.", reply_markup=kb_foreman_main())
        return
    await message.answer("Ваши объекты:", reply_markup=kb_sites_inline(sites))


@router.callback_query(F.data.startswith("f_site:"))
async def foreman_site_detail(callback: CallbackQuery, session: AsyncSession, current_user):
    site_id = int(callback.data.split(":")[1])
    from db.repo import get_site_by_id
    site = await get_site_by_id(session, site_id)
    if not site:
        await callback.answer("Объект не найден.", show_alert=True)
        return
    workers = [m.worker.name for m in site.members] if site.members else []
    workers_str = ", ".join(workers) if workers else "Нет рабочих"
    bot_info = await callback.bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={site.invite_code}"
    await callback.message.edit_text(
        f"🏗 <b>{site.name}</b>\n"
        f"📍 {site.address}\n"
        f"👷 Рабочие: {workers_str}\n\n"
        f"🔗 Инвайт-ссылка:\n<code>{invite_link}</code>"
    )
    await callback.answer()


@router.message(F.text == "➕ Создать объект")
async def foreman_create_site_start(message: Message, state: FSMContext):
    await message.answer("Введите название объекта:", reply_markup=kb_remove())
    await state.set_state(SiteCreateState.name)


@router.message(SiteCreateState.name)
async def foreman_site_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Теперь введите адрес объекта:")
    await state.set_state(SiteCreateState.address)


@router.message(SiteCreateState.address)
async def foreman_site_address(message: Message, state: FSMContext, session: AsyncSession, current_user):
    data = await state.get_data()
    await state.clear()
    code = generate_invite_code()
    site = await create_site(session, data["name"], message.text.strip(), current_user.id, code)
    bot_info = await message.bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={site.invite_code}"
    await message.answer(
        f"✅ Объект <b>{site.name}</b> создан!\n\n"
        f"🔗 Инвайт-ссылка для рабочих:\n<code>{invite_link}</code>",
        reply_markup=kb_foreman_main(),
    )
