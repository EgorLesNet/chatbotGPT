from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from db.models import UserRole, User, TaskReport
from db.repo import (
    get_sites_by_foreman, create_task, get_tasks_by_site,
    get_task_by_id, get_site_by_id, get_site_worker_telegram_ids
)
from keyboards.foreman import kb_foreman_main, kb_sites_inline, kb_tasks_inline, kb_task_foreman
from keyboards.common import kb_remove

router = Router()


class TaskCreateState(StatesGroup):
    site = State()
    title = State()
    description = State()


@router.message(F.text == "📋 Задачи")
async def foreman_tasks_menu(message: Message, session: AsyncSession, current_user):
    if not current_user or current_user.role != UserRole.foreman:
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer("Сначала создайте объект.", reply_markup=kb_foreman_main())
        return
    await message.answer("Выберите объект:", reply_markup=kb_sites_inline(sites, action="f_tasks"))


@router.callback_query(F.data.startswith("f_tasks:"))
async def foreman_tasks_list(callback: CallbackQuery, session: AsyncSession):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    active = [t for t in tasks if t.status.value != "done"]
    done_count = len([t for t in tasks if t.status.value == "done"])

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = kb_tasks_inline(active) if active else None

    archive_btn = InlineKeyboardButton(text=f"📦 Архив ({done_count})", callback_data=f"f_archive:{site_id}")
    if kb:
        kb.inline_keyboard.append([archive_btn])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[archive_btn]])

    text = "📋 Активные задачи:" if active else "Активных задач нет."
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("f_archive:"))
async def foreman_archive_list(callback: CallbackQuery, session: AsyncSession):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    done_tasks = [t for t in tasks if t.status.value == "done"]

    if not done_tasks:
        await callback.answer("Выполненных задач пока нет.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text=f"🟢 {t.title}", callback_data=f"f_arch_task:{t.id}")]
        for t in done_tasks
    ]
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data=f"f_tasks:{site_id}")])
    await callback.message.edit_text(
        "📦 <b>Архив выполненных задач:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("f_arch_task:"))
async def foreman_archive_task_detail(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    # Исполнитель
    worker_name = "неизвестно"
    if task.taken_by_id:
        res = await session.execute(select(User).where(User.id == task.taken_by_id))
        w = res.scalar_one_or_none()
        if w:
            worker_name = w.name

    # Отчёт
    res = await session.execute(select(TaskReport).where(TaskReport.task_id == task_id))
    report = res.scalar_one_or_none()

    text = (
        f"🟢 <b>{task.title}</b>\n"
        f"📝 {task.description or '—'}\n"
        f"👷 Исполнитель: {worker_name}\n"
    )
    if report:
        text += f"💬 Комментарий: {report.comment or '—'}\n"

    await callback.message.answer(text)

    # Фото из отчёта
    if report and report.photos_json:
        photos = json.loads(report.photos_json)
        for ph in photos:
            try:
                await bot.send_photo(callback.from_user.id, ph)
            except Exception:
                pass

    await callback.answer()


@router.callback_query(F.data.startswith("f_task:"))
async def foreman_task_detail(callback: CallbackQuery, session: AsyncSession):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return
    status_map = {"open": "🔵 Открыта", "in_progress": "🟡 В работе", "done": "🟢 Выполнена"}
    taken = ""
    if task.taken_by_id:
        res = await session.execute(select(User).where(User.id == task.taken_by_id))
        worker = res.scalar_one_or_none()
        taken = f"\nВыполняет: {worker.name}" if worker else ""
    await callback.message.edit_text(
        f"<b>{task.title}</b>\n\n{task.description}\n"
        f"Статус: {status_map.get(task.status.value, task.status.value)}{taken}",
        reply_markup=kb_task_foreman(task.id),
    )
    await callback.answer()


@router.message(F.text == "➕ Создать задачу")
async def foreman_create_task_start(message: Message, state: FSMContext, session: AsyncSession, current_user):
    if not current_user or current_user.role != UserRole.foreman:
        return
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer("Сначала создайте объект.", reply_markup=kb_foreman_main())
        return
    await message.answer("Для какого объекта задача?", reply_markup=kb_sites_inline(sites, action="f_newtask"))
    await state.set_state(TaskCreateState.site)


@router.callback_query(F.data.startswith("f_newtask:"), TaskCreateState.site)
async def foreman_pick_site(callback: CallbackQuery, state: FSMContext):
    site_id = int(callback.data.split(":")[1])
    await state.update_data(site_id=site_id)
    await callback.message.answer("Введите название задачи:", reply_markup=kb_remove())
    await state.set_state(TaskCreateState.title)
    await callback.answer()


@router.message(TaskCreateState.title)
async def foreman_task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Опишите задачу подробнее (или отправьте '-' чтобы пропустить):")
    await state.set_state(TaskCreateState.description)


@router.message(TaskCreateState.description)
async def foreman_task_desc(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot):
    data = await state.get_data()
    await state.clear()
    desc = message.text.strip() if message.text and message.text.strip() != "-" else ""
    task = await create_task(session, data["site_id"], data["title"], desc, current_user.id)
    worker_tg_ids = await get_site_worker_telegram_ids(session, data["site_id"])
    site = await get_site_by_id(session, data["site_id"])
    for tg_id in worker_tg_ids:
        try:
            await bot.send_message(
                tg_id,
                f"📌 Новая задача на объекте <b>{site.name if site else ''}</b>:\n"
                f"<b>{task.title}</b>\n{task.description}"
            )
        except Exception:
            pass
    await message.answer(f"✅ Задача <b>{task.title}</b> создана!", reply_markup=kb_foreman_main())
