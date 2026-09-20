from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import get_sites_by_foreman, get_user_by_phone, is_member, add_member
from filters.role import RoleFilter
from keyboards.foreman import kb_foreman_main, kb_sites_inline
from keyboards.common import kb_remove

router = Router()
router.message.filter(RoleFilter(UserRole.foreman))
router.callback_query.filter(RoleFilter(UserRole.foreman))


class AddWorkerState(StatesGroup):
    phone = State()
    site = State()


@router.message(F.text == "👷 Рабочие")
async def foreman_workers_menu(message: Message, state: FSMContext, session: AsyncSession, current_user):
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer("Сначала создайте объект.", reply_markup=kb_foreman_main())
        return
    await message.answer("📱 Введите номер телефона рабочего (7XXXXXXXXXX):", reply_markup=kb_remove())
    await state.set_state(AddWorkerState.phone)


@router.message(AddWorkerState.phone)
async def foreman_worker_phone(message: Message, state: FSMContext, session: AsyncSession, current_user):
    phone = (message.text or "").strip().replace("+", "")
    worker = await get_user_by_phone(session, phone)
    if not worker:
        await message.answer("Рабочий с таким номером не найден. Попросите его сначала зарегистрироваться в боте.")
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    await state.update_data(worker_id=worker.id, worker_name=worker.name)
    await message.answer(f"Выберите объект для {worker.name}:", reply_markup=kb_sites_inline(sites, action="f_addworker"))
    await state.set_state(AddWorkerState.site)


@router.callback_query(F.data.startswith("f_addworker:"), AddWorkerState.site)
async def foreman_add_worker_site(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    site_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    await state.clear()
    worker_id = data["worker_id"]
    worker_name = data["worker_name"]
    if await is_member(session, site_id, worker_id):
        await callback.message.answer(f"{worker_name} уже есть на этом объекте.")
    else:
        await add_member(session, site_id, worker_id)
        await callback.message.answer(f"✅ {worker_name} добавлен на объект.", reply_markup=kb_foreman_main())
    await callback.answer()
