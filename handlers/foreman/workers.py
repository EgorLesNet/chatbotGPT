from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import (
    get_sites_by_foreman, get_user_by_phone,
    get_site_by_id, is_member, add_member
)
from keyboards.foreman import kb_foreman_main, kb_sites_inline
from keyboards.common import kb_remove
from utils.invite import make_invite_link

router = Router()


class AddWorkerState(StatesGroup):
    select_site = State()
    phone_or_code = State()


@router.callback_query(F.data.startswith("f_addworker:"))
async def add_worker_start(callback: CallbackQuery, state: FSMContext, current_user):
    if not current_user or current_user.role != UserRole.foreman:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    site_id = int(callback.data.split(":")[1])
    await state.update_data(site_id=site_id)
    await callback.message.answer(
        "Введите номер телефона рабочего (например: 79001234567)\n"
        "или отправьте инвайт-ссылку рабочему сами — она уже готова в меню объекта.",
        reply_markup=kb_remove()
    )
    await state.set_state(AddWorkerState.phone_or_code)
    await callback.answer()


@router.message(AddWorkerState.phone_or_code)
async def add_worker_by_phone(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot):
    data = await state.get_data()
    await state.clear()
    phone = (message.text or "").strip().replace("+", "")
    site_id = data["site_id"]

    worker = await get_user_by_phone(session, phone)
    site = await get_site_by_id(session, site_id)

    if not worker:
        # Рабочий ещё не зарегистрирован — отправляем инвайт-ссылку
        bot_info = await bot.get_me()
        link = make_invite_link(bot_info.username, site.invite_code)
        await message.answer(
            f"⚠️ Пользователь с номером <code>{phone}</code> ещё не зарегистрирован.\n\n"
            f"Отправьте ему эту ссылку — при переходе он автоматически добавится к объекту:\n"
            f"<code>{link}</code>",
            reply_markup=kb_foreman_main(),
        )
        return

    if await is_member(session, site_id, worker.id):
        await message.answer(f"ℹ️ {worker.name} уже участник этого объекта.", reply_markup=kb_foreman_main())
        return

    await add_member(session, site_id, worker.id)
    try:
        await bot.send_message(
            worker.telegram_id,
            f"👷 Прораб <b>{current_user.name}</b> добавил вас на объект <b>{site.name}</b>!"
        )
    except Exception:
        pass
    await message.answer(
        f"✅ {worker.name} добавлен на объект <b>{site.name}</b>!",
        reply_markup=kb_foreman_main(),
    )
