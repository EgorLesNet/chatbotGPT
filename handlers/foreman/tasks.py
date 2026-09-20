from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import UserRole, User
from db.repo import (
    get_sites_by_foreman, create_task, get_tasks_by_site,
    get_task_by_id, get_site_by_id, get_site_worker_telegram_ids
)
from filters.role import RoleFilter
from keyboards.foreman import kb_foreman_main, kb_sites_inline, kb_tasks_inline, kb_task_foreman
from keyboards.common import kb_remove

router = Router()
router.message.filter(RoleFilter(UserRole.foreman))
router.callback_query.filter(RoleFilter(UserRole.foreman))


class TaskCreateState(StatesGroup):
    site = State()
    title = State()
    description = State()


@router.message(F.text == "📋 Задачи")
async def foreman_tasks_menu(message: Message, session: AsyncSession, current_user):
    sites = await get_sites_by_foreman(session, current_user.id)
    if not sites:
        await message.answer("Сначала создайте объект.", reply_markup=kb_foreman_main())
        return
    await message.answer("Выберите объект:", reply_markup=kb_sites_inline(sites, action="f_tasks"))


@router.callback_query(F.data.startswith("f_tasks:"))
async def foreman_tasks_list(callback: CallbackQuery, session: AsyncSession):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    if not tasks:
        await callback.message.edit_text("На этом объекте нет задач.")
        await callback.answer()
        return
    await callback.message.edit_text("📋 Задачи объекта:", reply_markup=kb_tasks_inline(tasks))
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
    await message.answer("Опишите задачу подробнее (или отправьте ‘-’ чтобы пропустить):")
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
