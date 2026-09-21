from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import get_sites_for_worker, get_recent_messages, save_message, get_site_by_id, get_all_site_participant_telegram_ids
from keyboards.worker import kb_worker_main, kb_sites_inline
from keyboards.common import kb_remove
from locales.i18n import t

router = Router()


class WorkerChatState(StatesGroup):
    site = State()
    chatting = State()


ALL_WORKER_CHAT_BTN = [t("btn_worker_chat", l) for l in ("ru", "en", "tg", "uz")]


@router.message(F.text.in_(ALL_WORKER_CHAT_BTN))
async def worker_chat_menu(message: Message, state: FSMContext, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.worker:
        return
    sites = await get_sites_for_worker(session, current_user.id)
    if not sites:
        await message.answer(t("no_sites_worker", lang), reply_markup=kb_worker_main(lang))
        return
    await message.answer(t("select_site_chat", lang), reply_markup=kb_sites_inline(sites, action="w_chat"))
    await state.set_state(WorkerChatState.site)


@router.callback_query(F.data.startswith("w_chat:"), WorkerChatState.site)
async def worker_chat_enter(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str):
    site_id = int(callback.data.split(":")[1])
    await state.update_data(site_id=site_id)
    site = await get_site_by_id(session, site_id)
    messages = await get_recent_messages(session, site_id)
    history = "".join(
        f"<b>{m.sender.name}</b>: {m.text}\n" for m in messages
    ) or t("no_messages", lang)
    await callback.message.answer(
        t("chat_header", lang, name=site.name if site else "", history=history),
        reply_markup=kb_remove()
    )
    await state.set_state(WorkerChatState.chatting)
    await callback.answer()


@router.message(WorkerChatState.chatting)
async def worker_chat_message(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot, lang: str):
    if message.text and message.text.startswith("/"):
        await state.clear()
        await message.answer(t("welcome_back", lang, name=current_user.name), reply_markup=kb_worker_main(lang))
        return
    data = await state.get_data()
    site_id = data.get("site_id")
    site = await get_site_by_id(session, site_id)
    text = message.text or ""
    await save_message(session, site_id, current_user.id, text)
    all_ids = await get_all_site_participant_telegram_ids(session, site)
    for tg_id in all_ids:
        if tg_id == message.from_user.id:
            continue
        try:
            await bot.send_message(
                tg_id,
                t("chat_message", lang, name=current_user.name, site=site.name if site else "", text=text)
            )
        except Exception:
            pass
