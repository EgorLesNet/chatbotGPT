from aiogram import Router, F, Bot
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import (
    get_sites_by_foreman, get_site_by_id,
    save_message, get_recent_messages, get_all_site_participant_telegram_ids
)
from keyboards.foreman import kb_foreman_main, kb_sites_inline
from keyboards.common import kb_remove

router = Router()
router.message.filter(F.func(lambda _, d: d.get("current_user") and d["current_user"].role == UserRole.foreman))
router.callback_query.filter(F.func(lambda _, d: d.get("current_user") and d["current_user"].role == UserRole.foreman))


class ForemanChatState(StatesGroup):
    select_site = State()
    chatting = State()


@router.message(F.text == "💬 Чат")
async def chat_menu(message: Message, state: FSMContext, session: AsyncSession, current_user):
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer("Сначала создайте объект.", reply_markup=kb_foreman_main())
        return
    await message.answer("Выберите объект для чата:", reply_markup=kb_sites_inline(sites, action="f_chat"))


@router.callback_query(F.data.startswith("f_chat:"))
async def enter_chat(callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user):
    site_id = int(callback.data.split(":")[1])
    await state.update_data(chat_site_id=site_id)
    await state.set_state(ForemanChatState.chatting)

    msgs = await get_recent_messages(session, site_id, limit=10)
    history = ""
    for m in msgs:
        sender = m.sender.name if m.sender else "?"
        history += f"<b>{sender}:</b> {m.text}\n"

    site = await get_site_by_id(session, site_id)
    await callback.message.answer(
        f"💬 Чат объекта <b>{site.name}</b>\n\n"
        + (history if history else "(Сообщений пока нет)\n") +
        "\nПишите сообщение — оно отправится всем участникам.\n"
        "Чтобы выйти из чата, нажмите /start",
        reply_markup=kb_remove(),
    )
    await callback.answer()


@router.message(ForemanChatState.chatting)
async def foreman_send_chat(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot):
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
