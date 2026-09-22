from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from db.models import UserRole, User, TaskReport, TaskStatus
from db.repo import (
    get_sites_by_foreman, create_task, get_tasks_by_site,
    get_task_by_id, get_site_by_id, get_site_worker_telegram_ids,
    get_report_by_task, create_task_review, return_task_to_work, complete_task
)
from keyboards.foreman import kb_foreman_main, kb_sites_inline, kb_tasks_inline, kb_task_foreman, kb_review_actions
from keyboards.common import kb_remove
from locales.i18n import t

router = Router()


class TaskCreateState(StatesGroup):
    site = State()
    title = State()
    description = State()
    photo = State()


class ReviewCommentState(StatesGroup):
    comment = State()


ALL_TASKS_BTN = [t("btn_tasks", l) for l in ("ru", "en", "tg", "uz")]
ALL_CREATE_TASK_BTN = [t("btn_create_task", l) for l in ("ru", "en", "tg", "uz")]


@router.message(F.text.in_(ALL_TASKS_BTN))
async def foreman_tasks_menu(message: Message, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.foreman:
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer(t("no_sites_first", lang), reply_markup=kb_foreman_main(lang))
        return
    await message.answer(t("select_site", lang), reply_markup=kb_sites_inline(sites, action="f_tasks"))


@router.callback_query(F.data.startswith("f_tasks:"))
async def foreman_tasks_list(callback: CallbackQuery, session: AsyncSession, lang: str):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    active = [t_ for t_ in tasks if t_.status.value != "done"]
    done_count = len([t_ for t_ in tasks if t_.status.value == "done"])

    kb = kb_tasks_inline(active) if active else None
    archive_btn = InlineKeyboardButton(
        text=t("archive_btn", lang, count=done_count),
        callback_data=f"f_archive:{site_id}"
    )
    if kb:
        kb.inline_keyboard.append([archive_btn])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[archive_btn]])

    text = t("active_tasks", lang) if active else t("no_active_tasks", lang)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("f_archive:"))
async def foreman_archive_list(callback: CallbackQuery, session: AsyncSession, lang: str):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    done_tasks = [t_ for t_ in tasks if t_.status.value == "done"]
    if not done_tasks:
        await callback.answer(t("no_done_tasks", lang), show_alert=True)
        return
    buttons = [
        [InlineKeyboardButton(text=f"🟢 {t_.title}", callback_data=f"f_arch_task:{t_.id}")]
        for t_ in done_tasks
    ]
    buttons.append([InlineKeyboardButton(text=t("back_btn", lang), callback_data=f"f_tasks:{site_id}")])
    await callback.message.edit_text(
        t("archive_title", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("f_arch_task:"))
async def foreman_archive_task_detail(callback: CallbackQuery, session: AsyncSession, bot: Bot, lang: str):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer(t("task_not_found", lang), show_alert=True)
        return
    worker_name = "?"
    if task.taken_by_id:
        res = await session.execute(select(User).where(User.id == task.taken_by_id))
        w = res.scalar_one_or_none()
        if w:
            worker_name = w.name
    report = await get_report_by_task(session, task_id)
    text = (
        f"🟢 <b>{task.title}</b>\n"
        f"📝 {task.description or '—'}\n"
        + t("arch_executor", lang, name=worker_name) + "\n"
    )
    if report:
        text += t("arch_comment", lang, comment=report.comment or "—") + "\n"
    await callback.message.answer(text)
    if task.photo_id:
        try:
            await bot.send_photo(callback.from_user.id, task.photo_id)
        except Exception:
            pass
    if report and report.photos_json:
        photos = json.loads(report.photos_json)
        for ph in photos:
            try:
                await bot.send_photo(callback.from_user.id, ph)
            except Exception:
                pass
    await callback.answer()


@router.callback_query(F.data.startswith("f_task:"))
async def foreman_task_detail(callback: CallbackQuery, session: AsyncSession, bot: Bot, lang: str):
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
        reply_markup=kb_review_actions(task.id, lang) if task.status == TaskStatus.review else kb_task_foreman(task.id, lang),
    )
    if task.photo_id:
        try:
            await bot.send_photo(callback.from_user.id, task.photo_id, caption=t("task_area_photo", lang))
        except Exception:
            pass
    report = await get_report_by_task(session, task.id)
    if task.status == TaskStatus.review and report and report.photos_json:
        photos = json.loads(report.photos_json)
        for ph in photos:
            try:
                await bot.send_photo(callback.from_user.id, ph)
            except Exception:
                pass
        if report.comment:
            await callback.message.answer(t("worker_report_comment", lang, comment=report.comment))
    await callback.answer()


@router.message(F.text.in_(ALL_CREATE_TASK_BTN))
async def foreman_create_task_start(message: Message, state: FSMContext, session: AsyncSession, current_user, lang: str):
    if not current_user or current_user.role != UserRole.foreman:
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer(t("no_sites_first", lang), reply_markup=kb_foreman_main(lang))
        return
    await message.answer(t("select_site", lang), reply_markup=kb_sites_inline(sites, action="f_newtask"))
    await state.set_state(TaskCreateState.site)


@router.callback_query(F.data.startswith("f_newtask:"), TaskCreateState.site)
async def foreman_pick_site(callback: CallbackQuery, state: FSMContext, lang: str):
    site_id = int(callback.data.split(":")[1])
    await state.update_data(site_id=site_id)
    await callback.message.answer(t("enter_task_name", lang), reply_markup=kb_remove())
    await state.set_state(TaskCreateState.title)
    await callback.answer()


@router.message(TaskCreateState.title)
async def foreman_task_title(message: Message, state: FSMContext, lang: str):
    await state.update_data(title=message.text.strip())
    await message.answer(t("enter_task_desc", lang))
    await state.set_state(TaskCreateState.description)


@router.message(TaskCreateState.description)
async def foreman_task_desc(message: Message, state: FSMContext, lang: str):
    desc = message.text.strip() if message.text and message.text.strip() != "-" else ""
    await state.update_data(description=desc)
    await message.answer(t("send_task_photo", lang))
    await state.set_state(TaskCreateState.photo)


@router.message(TaskCreateState.photo, F.photo)
async def foreman_task_photo(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot, lang: str):
    data = await state.get_data()
    await state.clear()
    task = await create_task(session, data["site_id"], data["title"], data["description"], current_user.id, message.photo[-1].file_id)
    worker_tg_ids = await get_site_worker_telegram_ids(session, data["site_id"])
    site = await get_site_by_id(session, data["site_id"])
    for tg_id in worker_tg_ids:
        w_lang = await get_worker_lang_by_tg(session, tg_id)
        try:
            await bot.send_message(tg_id, t("new_task_notify", w_lang, site=site.name if site else "", title=task.title, desc=task.description))
            await bot.send_photo(tg_id, task.photo_id, caption=t("task_area_photo", w_lang))
        except Exception:
            pass
    await message.answer(t("task_created", lang, title=task.title), reply_markup=kb_foreman_main(lang))


@router.message(TaskCreateState.photo)
async def foreman_task_photo_skip(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot, lang: str):
    skip_words = [t("skip_word", l) for l in ("ru", "en", "tg", "uz")]
    if (message.text or "").strip().lower() not in skip_words:
        await message.answer(t("send_task_photo", lang))
        return
    data = await state.get_data()
    await state.clear()
    task = await create_task(session, data["site_id"], data["title"], data["description"], current_user.id)
    worker_tg_ids = await get_site_worker_telegram_ids(session, data["site_id"])
    site = await get_site_by_id(session, data["site_id"])
    for tg_id in worker_tg_ids:
        w_lang = await get_worker_lang_by_tg(session, tg_id)
        try:
            await bot.send_message(tg_id, t("new_task_notify", w_lang, site=site.name if site else "", title=task.title, desc=task.description))
        except Exception:
            pass
    await message.answer(t("task_created", lang, title=task.title), reply_markup=kb_foreman_main(lang))


@router.callback_query(F.data.startswith("f_rework:"))
async def foreman_rework_start(callback: CallbackQuery, state: FSMContext, lang: str):
    task_id = int(callback.data.split(":")[1])
    await state.update_data(review_task_id=task_id)
    await callback.message.answer(t("enter_review_comment", lang), reply_markup=kb_remove())
    await state.set_state(ReviewCommentState.comment)
    await callback.answer()


@router.message(ReviewCommentState.comment)
async def foreman_rework_comment(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot, lang: str):
    data = await state.get_data()
    await state.clear()
    task_id = data["review_task_id"]
    comment = message.text.strip() if message.text else ""
    task = await get_task_by_id(session, task_id)
    if not task:
        await message.answer(t("task_not_found", lang), reply_markup=kb_foreman_main(lang))
        return
    await create_task_review(session, task_id, current_user.id, comment)
    await return_task_to_work(session, task_id)
    if task.taken_by_id:
        res = await session.execute(select(User).where(User.id == task.taken_by_id))
        worker = res.scalar_one_or_none()
        if worker:
            try:
                await bot.send_message(worker.telegram_id, t("task_rework_needed", worker.lang or "ru", title=task.title, comment=comment))
            except Exception:
                pass
    await message.answer(t("task_sent_to_rework", lang), reply_markup=kb_foreman_main(lang))


@router.callback_query(F.data.startswith("f_accept:"))
async def foreman_accept_task(callback: CallbackQuery, session: AsyncSession, bot: Bot, lang: str):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer(t("task_not_found", lang), show_alert=True)
        return
    await complete_task(session, task_id)
    if task.taken_by_id:
        res = await session.execute(select(User).where(User.id == task.taken_by_id))
        worker = res.scalar_one_or_none()
        if worker:
            try:
                await bot.send_message(worker.telegram_id, t("task_accepted", worker.lang or "ru", title=task.title))
            except Exception:
                pass
    await callback.message.answer(t("task_review_accepted", lang))
    await callback.answer()


async def get_worker_lang_by_tg(session, tg_id: int) -> str:
    from sqlalchemy import select as sa_select
    from db.models import User as U
    res = await session.execute(sa_select(U.lang).where(U.telegram_id == tg_id))
    lang = res.scalar_one_or_none()
    return lang or "ru"
