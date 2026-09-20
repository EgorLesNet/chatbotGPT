from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import (
    get_sites_by_foreman, get_tasks_by_site, get_task_by_id,
    create_task, get_site_worker_telegram_ids, get_site_by_id
)
from keyboards.foreman import kb_foreman_main, kb_sites_inline, kb_tasks_inline
from keyboards.common import kb_remove
from utils.notify import notify_many

router = Router()


class NewTaskState(StatesGroup):
    site_id = State()
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
    await message.answer("Выберите объект для просмотра задач:", reply_markup=kb_sites_inline(sites, action="f_tasks"))


@router.callback_query(F.data.startswith("f_tasks:"))
async def foreman_tasks_list(callback: CallbackQuery, session: AsyncSession, current_user):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    if not tasks:
        await callback.message.edit_text("На этом объекте пока нет задач.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "📋 Задачи объекта:",
        reply_markup=kb_tasks_inline(tasks, prefix="f_task"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("f_task:"))
async def foreman_task_detail(callback: CallbackQuery, session: AsyncSession):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return
    status_map = {"open": "🔵 Открыта", "in_progress": "🟡 В работе", "done": "🟢 Выполнена"}
    taken = f"\n👷 Исполнитель: #{task.taken_by_id}" if task.taken_by_id else ""
    await callback.message.edit_text(
        f"<b>{task.title}</b>\n\n{task.description}\n\n"
        f"Статус: {status_map.get(task.status.value, task.status.value)}{taken}"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("f_newtask:"))
async def foreman_new_task_start(callback: CallbackQuery, state: FSMContext):
    site_id = int(callback.data.split(":")[1])
    await state.update_data(site_id=site_id)
    await callback.message.answer("Введите название задачи:", reply_markup=kb_remove())
    await state.set_state(NewTaskState.title)
    await callback.answer()


@router.message(NewTaskState.title)
async def new_task_title(message: Message, state: FSMContext):
    await state.update_data(title=(message.text or "").strip())
    await message.answer("Введите описание задачи (или отправьте '-' чтобы пропустить):")
    await state.set_state(NewTaskState.description)


@router.message(NewTaskState.description)
async def new_task_description(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot):
    data = await state.get_data()
    await state.clear()
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""
    task = await create_task(session, data["site_id"], data["title"], desc, current_user.id)
    site = await get_site_by_id(session, data["site_id"])
    await message.answer(
        f"✅ Задача <b>{task.title}</b> создана!",
        reply_markup=kb_foreman_main(),
    )
    # Уведомить рабочих
    worker_ids = await get_site_worker_telegram_ids(session, task.site_id)
    site_name = site.name if site else "объект"
    await notify_many(
        bot, worker_ids,
        f"🔵 Новая задача на объекте <b>{site_name}</b>:\n<b>{task.title}</b>\n{task.description}",
        exclude=current_user.telegram_id,
    )
