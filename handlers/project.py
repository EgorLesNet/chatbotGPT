from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from utils.storage import create_project, ensure_user, get_user_projects, reset_user_month
from utils.subscription import can_create_project, get_plan_limits
from utils.keyboards import back_kb

router = Router()


class ProjectForm(StatesGroup):
    title = State()
    project_type = State()
    area = State()
    notes = State()


TYPE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Квартира"), KeyboardButton(text="Дом")],
        [KeyboardButton(text="Офис"), KeyboardButton(text="Коммерция")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def _projects_text(projects: list[dict]) -> str:
    lines = ["📁 <b>Проекты</b>"]
    for p in projects[-10:]:
        est_count = len(p.get("estimates", []))
        est_label = f" · 📋 {est_count} сметы" if est_count else ""
        lines.append(
            f"• <b>{p['title']}</b> — {p['project_type']}, {p['area_m2']} м²"
            f", {p['created_at'][:10]}{est_label}"
        )
    return "\n".join(lines)


@router.callback_query(F.data == "nav:projects")
async def cb_nav_projects(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    reset_user_month(user["id"])
    existing = get_user_projects(user["id"])
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    if existing:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новый проект", callback_data="project:new")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")],
        ])
        await call.message.answer(_projects_text(existing), reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать проект", callback_data="project:new")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")],
        ])
        await call.message.answer("📁 Проектов пока нет.", reply_markup=kb)


@router.callback_query(F.data == "project:new")
async def cb_project_new(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    reset_user_month(user["id"])
    await _start_create(call.message, state, user)


@router.message(Command("project"))
async def cmd_project(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    existing = get_user_projects(user["id"])
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    if existing:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новый проект", callback_data="project:new")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")],
        ])
        await message.answer(_projects_text(existing), reply_markup=kb)
    else:
        await _start_create(message, state, user)


@router.message(Command("newproject"))
async def cmd_new_project(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    await _start_create(message, state, user)


async def _start_create(message: Message, state: FSMContext, user: dict) -> None:
    if not can_create_project(user):
        limits = get_plan_limits(user)
        await message.answer(
            "🚫 Лимит free-плана исчерпан.\n"
            f"Максимум <b>{limits['projects_per_month_label']}</b> проект(а) в месяц.\n"
            "Оформи paid: /subscribe",
            reply_markup=back_kb(),
        )
        return
    await state.set_state(ProjectForm.title)
    await message.answer(
        "🏗 <b>Новый проект</b>\n\nШаг 1/4 — название объекта:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ProjectForm.title)
async def step_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(ProjectForm.project_type)
    await message.answer("Шаг 2/4 — тип объекта:", reply_markup=TYPE_KB)


@router.message(ProjectForm.project_type)
async def step_type(message: Message, state: FSMContext) -> None:
    await state.update_data(project_type=message.text.strip())
    await state.set_state(ProjectForm.area)
    await message.answer("Шаг 3/4 — площадь в м²:", reply_markup=ReplyKeyboardRemove())


@router.message(ProjectForm.area)
async def step_area(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".")
    try:
        area = int(float(raw))
        if area <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи корректное число, например: 42")
        return
    await state.update_data(area=area)
    await state.set_state(ProjectForm.notes)
    await message.answer("Шаг 4/4 — комментарий к объекту (или <b>-</b> чтобы пропустить):")


@router.message(ProjectForm.notes)
async def step_notes(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    notes = message.text.strip()
    if notes == "-":
        notes = ""
    user = ensure_user(message.from_user)
    project = create_project(
        user_id=user["id"],
        title=data["title"],
        project_type=data["project_type"],
        area_m2=data["area"],
        notes=notes,
    )
    await state.clear()
    await message.answer(
        f"✅ Проект <b>{project['title']}</b> создан!\n"
        f"🏠 {project['project_type']} · 📐 {project['area_m2']} м²\n"
        f"📝 {project['notes'] or '—'}",
        reply_markup=back_kb(),
    )
