from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import get_user_by_phone, get_sites_by_foreman, is_member, add_member
from keyboards.foreman import kb_foreman_main, kb_sites_inline
from keyboards.common import kb_remove
from locales.i18n import t

router = Router()


class AddWorkerState(StatesGroup):
    phone = State()
    site = State()


ALL_WORKERS_BTN = [t("btn_workers", l) for l in ("ru", "en", "tg", "uz")]


@router.message(F.text.in_(ALL_WORKERS_BTN))
async def foreman_workers_menu(message: Message, state: FSMContext, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.foreman:
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer(t("no_sites_first", lang), reply_markup=kb_foreman_main(lang))
        return
    await message.answer(t("enter_worker_phone", lang), reply_markup=kb_remove())
    await state.set_state(AddWorkerState.phone)


@router.message(AddWorkerState.phone)
async def foreman_worker_phone(message: Message, state: FSMContext, session: AsyncSession, current_user, lang: str):
    phone = message.text.strip().lstrip("+")
    worker = await get_user_by_phone(session, phone)
    if not worker or worker.role != UserRole.worker:
        await message.answer(t("worker_not_found", lang))
        await state.clear()
        return
    await state.update_data(worker_id=worker.id, worker_name=worker.name)
    sites = await get_sites_by_foreman(session, current_user.id)
    await message.answer(t("select_site_for_worker", lang, name=worker.name), reply_markup=kb_sites_inline(sites, action="f_addworker"))
    await state.set_state(AddWorkerState.site)


@router.callback_query(F.data.startswith("f_addworker:"), AddWorkerState.site)
async def foreman_worker_add_to_site(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str):
    data = await state.get_data()
    await state.clear()
    site_id = int(callback.data.split(":")[1])
    worker_id = data["worker_id"]
    worker_name = data["worker_name"]
    if await is_member(session, site_id, worker_id):
        await callback.message.answer(t("worker_already_on_site", lang, name=worker_name))
        await callback.answer()
        return
    await add_member(session, site_id, worker_id)
    await callback.message.answer(t("worker_added", lang, name=worker_name))
    await callback.answer()
