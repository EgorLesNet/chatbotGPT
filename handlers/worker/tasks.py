from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from db.models import UserRole, User, TaskStatus
from db.repo import (
    get_sites_for_worker, get_tasks_by_site, get_task_by_id,
    take_task, send_task_to_review, create_report, get_site_by_id, get_last_task_review
)
from keyboards.worker import kb_worker_main, kb_sites_inline, kb_task_worker, kb_tasks_inline
from keyboards.common import kb_remove
from locales.i18n import t

router = Router()


class DoneTaskState(StatesGroup):
    photos = State()
    comment = State()


ALL_WORKER_TASKS_BTN = [t("btn_worker_tasks", l) for l in ("ru", "en", "tg", "uz")]


@router.message(F.text.in_(ALL_WORKER_TASKS_BTN))
async def worker_tasks_menu(message: Message, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.worker:
        return
    sites = await get_sites_for_worker(session, current_user.id)
    if not sites:
        await message.answer(t("no_sites_worker", lang), reply_markup=kb_worker_main(lang))
        return
    await message.answer(t("select_site", lang), reply_markup=kb_sites_inline(sites, action="w_tasks"))


@router.callback_query(F.data.startswith("w_tasks:"))
async def worker_tasks_list(callback: CallbackQuery, session: AsyncSession, lang: str):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    active = [t_ for t_ in tasks if t_.status.value != "done"]
    if not active:
        await callback.answer(t("no_active_tasks_worker", lang), show_alert=True)
        return
    await callback.message.edit_text(t("active_tasks", lang), reply_markup=kb_tasks_inline(active, prefix="w_task"))
    await callback.answer()


@router.callback_query(F.data.startswith("w_task:"))
async def worker_task_detail(callback: CallbackQuery, session: AsyncSession, bot: Bot, lang: str):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer(t("task_not_found", lang), show_alert=True)
        return
    status_key = {
        "open": "status_open",
        "in_progress": "status_in_progress",
        "review": "status_review",
        "done": "status_done"
    }
    status_str = t(status_key.get(task.status.value, "status_open"), lang)
    taken_str = ""
    if task.taken_by_id:
        res = await session.execute(select(User).where(User.id == task.taken_by_id))
        worker = res.scalar_one_or_none()
        taken_str = t("task_detail_worker", lang, name=worker.name) if worker else ""
    await callback.message.edit_text(
        t("task_detail", lang, title=task.title, desc=task.description or "—", status=status_str) + taken_str,
        reply_markup=kb_task_worker(task.id, task.status.value, lang),
    )
    if task.photo_id:
        try:
            await bot.send_photo(callback.from_user.id, task.photo_id, caption=t("task_area_photo", lang))
        except Exception:
            pass
    last_review = await get_last_task_review(session, task.id)
    if last_review and task.status == TaskStatus.in_progress:
        await callback.message.answer(t("last_review_comment", lang, comment=last_review.comment))
    await callback.answer()


@router.callback_query(F.data.startswith("w_take:"))
async def worker_take_task(callback: CallbackQuery, session: AsyncSession, current_user, bot: Bot, lang: str):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task or task.status != TaskStatus.open:
        await callback.answer(t("task_already_taken", lang), show_alert=True)
        return
    await take_task(session, task_id, current_user.id)
    site = await get_site_by_id(session, task.site_id)
    foreman_result = await session.execute(select(User).where(User.id == site.foreman_id))
    foreman = foreman_result.scalar_one_or_none()
    if foreman:
        f_lang = foreman.lang or "ru"
        try:
            await bot.send_message(
                foreman.telegram_id,
                t("task_taken_notify", f_lang, worker=current_user.name, task=task.title, site=site.name if site else "")
            )
        except Exception:
            pass
    await callback.message.edit_text(t("task_taken", lang, title=task.title))
    await callback.answer()


@router.callback_query(F.data.startswith("w_done:"))
async def worker_done_task_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task or task.status != TaskStatus.in_progress:
        await callback.answer(t("task_not_found", lang), show_alert=True)
        return
    await state.update_data(task_id=task_id)
    await callback.message.answer(t("send_min_3_photos", lang), reply_markup=kb_remove())
    await state.set_state(DoneTaskState.photos)
    await callback.answer()


@router.message(DoneTaskState.photos, F.photo)
async def worker_collect_photos(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    if len(photos) >= 5:
        await message.answer(t("enter_comment", lang), reply_markup=kb_remove())
        await state.set_state(DoneTaskState.comment)
    else:
        await message.answer(t("photo_received", lang, n=len(photos)))


@router.message(DoneTaskState.photos)
async def worker_photos_done_word(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    photos = data.get("photos", [])
    done_words = [t("done_word", l) for l in ("ru", "en", "tg", "uz")]
    if message.text and message.text.strip().lower() in done_words:
        if len(photos) < 3:
            await message.answer(t("need_min_3_photos", lang))
            return
        await message.answer(t("enter_comment", lang), reply_markup=kb_remove())
        await state.set_state(DoneTaskState.comment)
    else:
        await message.answer(t("send_min_3_photos", lang))


@router.message(DoneTaskState.comment)
async def worker_submit_report(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot, lang: str):
    data = await state.get_data()
    await state.clear()
    task_id = data["task_id"]
    photos = data.get("photos", [])
    comment = message.text.strip() if message.text else ""
    await send_task_to_review(session, task_id)
    await create_report(session, task_id, current_user.id, comment, photos)
    task = await get_task_by_id(session, task_id)
    site = await get_site_by_id(session, task.site_id) if task else None
    foreman_result = await session.execute(select(User).where(User.id == site.foreman_id))
    foreman = foreman_result.scalar_one_or_none()
    if foreman:
        f_lang = foreman.lang or "ru"
        notify_text = t("report_notify_review", f_lang, worker=current_user.name, task=task.title if task else "", site=site.name if site else "", comment=comment)
        try:
            await bot.send_message(foreman.telegram_id, notify_text)
        except Exception:
            pass
        for ph in photos:
            try:
                await bot.send_photo(foreman.telegram_id, ph)
            except Exception:
                pass
    await message.answer(t("report_sent_review", lang), reply_markup=kb_worker_main(lang))
