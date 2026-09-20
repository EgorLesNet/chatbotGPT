from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import (
    get_sites_for_worker, get_site_by_id,
    save_message, get_recent_messages, get_all_site_participant_telegram_ids
)
from keyboards.worker import kb_worker_main, kb_sites_inline
from keyboards.common import kb_remove

router = Router()
router.message.filter(F.func(lambda _, d: d.get("current_user") and d["current_user"].role == UserRole.worker))
router.callback_query.filter(F.func(lambda _, d: d.get("current_user") and d["current_user"].role == UserRole.worker))


class WorkerChatState(StatesGroup):
    chatting = State()


@router.message(F.text == "💬 Чат")
async def worker_chat_menu(message: Message, state: FSMContext, session: AsyncSession, current_user):
    sites = await get_sites_for_worker(session, current_user.id)
    if not sites:
        await message.answer("Вы не состоите ни в одном объекте.", reply_markup=kb_worker_main())
        return
    if len(sites) == 1:
        await _enter_chat(message, state, session, current_user, sites[0].id)
    else:
        await message.answer("Выберите объект для чата:", reply_markup=kb_sites_inline(sites, action="w_chat"))


@router.callback_query(F.data.startswith("w_chat:"))
async def worker_enter_chat_cb(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user):
    site_id = int(callback.data.split(":")[1])
    await _enter_chat(callback.message, state, session, current_user, site_id)
    await callback.answer()


async def _enter_chat(message: Message, state: FSMContext, session, current_user, site_id: int):
    await state.update_data(chat_site_id=site_id)
    await state.set_state(WorkerChatState.chatting)
    msgs = await get_recent_messages(session, site_id, limit=10)
    history = ""
    for m in msgs:
        sender = m.sender.name if m.sender else "?"
        history += f"<b>{sender}:</b> {m.text}\n"
    site = await get_site_by_id(session, site_id)
    await message.answer(
        f"💬 Чат объекта <b>{site.name}</b>\n\n"
        + (history if history else "(Сообщений пока нет)\n") +
        "\nПишите — сообщение получат все участники.\n/start — выйти из чата.",
        reply_markup=kb_remove(),
    )


@router.message(WorkerChatState.chatting)
async def worker_send_chat(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot):
    data = await state.get_data()
    site_id = data.get("chat_site_id")
    if not site_id:
        return
    site = await get_site_by_id(session, site_id)
    if not site:
        return
    text = message.text or ""
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = message.caption or ""
    await save_message(session, site_id, current_user.id, text, photo_id)
    tg_ids = await get_all_site_participant_telegram_ids(session, site)
    for tg_id in tg_ids:
        if tg_id == current_user.telegram_id:
            continue
        try:
            msg_text = f"💬 <b>{current_user.name}</b> [{site.name}]:\n{text}"
            if photo_id:
                await bot.send_photo(tg_id, photo_id, caption=msg_text)
            else:
                await bot.send_message(tg_id, msg_text)
        except Exception:
            pass
