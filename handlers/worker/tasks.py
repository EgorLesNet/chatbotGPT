from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import UserRole, User
from db.repo import (
    get_sites_for_worker, get_tasks_by_site,
    get_task_by_id, take_task, complete_task, create_report, get_site_by_id
)
from keyboards.worker import kb_worker_main, kb_sites_inline, kb_tasks_inline, kb_task_worker
from keyboards.common import kb_remove

router = Router()
router.message.filter(F.func(lambda _, d: d.get("current_user") and d["current_user"].role == UserRole.worker))
router.callback_query.filter(F.func(lambda _, d: d.get("current_user") and d["current_user"].role == UserRole.worker))


class ReportState(StatesGroup):
    task_id = State()
    photos = State()
    comment = State()


@router.message(F.text == "📋 Задачи")
async def worker_tasks_menu(message: Message, session: AsyncSession, current_user):
    sites = await get_sites_for_worker(session, current_user.id)
    if not sites:
        await message.answer("Вы не состоите ни в одном объекте.", reply_markup=kb_worker_main())
        return
    await message.answer("Выберите объект:", reply_markup=kb_sites_inline(sites, action="w_tasks"))


@router.callback_query(F.data.startswith("w_tasks:"))
async def worker_tasks_list(callback: CallbackQuery, session: AsyncSession):
    site_id = int(callback.data.split(":")[1])
    tasks = await get_tasks_by_site(session, site_id)
    open_tasks = [t for t in tasks if t.status.value != "done"]
    if not open_tasks:
        await callback.message.edit_text("На этом объекте нет активных задач.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "📋 Задачи объекта:",
        reply_markup=kb_tasks_inline(open_tasks, prefix="w_task"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("w_task:"))
async def worker_task_detail(callback: CallbackQuery, session: AsyncSession):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return
    status_map = {"open": "🔵 Открыта", "in_progress": "🟡 В работе", "done": "🟢 Выполнена"}
    await callback.message.edit_text(
        f"<b>{task.title}</b>\n\n{task.description}\n\nСтатус: {status_map.get(task.status.value, task.status.value)}",
        reply_markup=kb_task_worker(task.id, task.status.value),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("w_take:"))
async def worker_take_task(callback: CallbackQuery, session: AsyncSession, current_user, bot: Bot):
    task_id = int(callback.data.split(":")[1])
    task = await get_task_by_id(session, task_id)
    if not task or task.status.value != "open":
        await callback.answer("Задача уже занята или не найдена.", show_alert=True)
        return
    await take_task(session, task_id, current_user.id)
    site = await get_site_by_id(session, task.site_id)
    if site:
        res = await session.execute(select(User).where(User.id == site.foreman_id))
        foreman = res.scalar_one_or_none()
        if foreman:
            try:
                await bot.send_message(
                    foreman.telegram_id,
                    f"▶️ <b>{current_user.name}</b> взял задачу <b>{task.title}</b> на объекте <b>{site.name}</b>."
                )
            except Exception:
                pass
    await callback.message.edit_text(
        f"✅ Вы взяли задачу <b>{task.title}</b>. Выполняйте и отметьте результат.",
        reply_markup=kb_task_worker(task_id, "in_progress"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("w_done:"))
async def worker_done_start(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    await state.update_data(task_id=task_id, photos=[])
    await callback.message.answer(
        "📸 Отправьте фото выполненной работы (1–5 фото).\n"
        "Когда закончите — напишите <b>готово</b>.",
        reply_markup=kb_remove(),
    )
    await state.set_state(ReportState.photos)
    await callback.answer()


@router.message(ReportState.photos, F.photo)
async def collect_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: list = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"📸 Фото {len(photos)} получено. Ещё фото или напишите <b>готово</b>.")


@router.message(ReportState.photos, F.text.lower() == "готово")
async def photos_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos"):
        await message.answer("Нужно хотя бы одно фото.")
        return
    await message.answer("Напишите краткий комментарий к выполненной работе:")
    await state.set_state(ReportState.comment)


@router.message(ReportState.comment)
async def save_report(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot):
    data = await state.get_data()
    await state.clear()
    task_id = data["task_id"]
    photos = data.get("photos", [])
    comment = (message.text or "").strip()

    await create_report(session, task_id, current_user.id, comment, photos)
    await complete_task(session, task_id)

    task = await get_task_by_id(session, task_id)
    site = await get_site_by_id(session, task.site_id) if task else None

    await message.answer(
        "✅ Отчёт отправлен! Задача отмечена выполненной.",
        reply_markup=kb_worker_main(),
    )

    if site:
        res = await session.execute(select(User).where(User.id == site.foreman_id))
        foreman = res.scalar_one_or_none()
        if foreman:
            try:
                text = (
                    f"🟢 <b>{current_user.name}</b> выполнил задачу <b>{task.title}</b>\n"
                    f"Объект: {site.name}\n"
                    f"Комментарий: {comment}"
                )
                if photos:
                    await bot.send_photo(foreman.telegram_id, photos[0], caption=text)
                    for ph in photos[1:]:
                        await bot.send_photo(foreman.telegram_id, ph)
                else:
                    await bot.send_message(foreman.telegram_id, text)
            except Exception:
                pass
