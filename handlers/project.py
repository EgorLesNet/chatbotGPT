from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from utils.storage import create_project, ensure_user, get_user_projects, reset_user_month
from utils.subscription import can_create_project, get_plan_limits

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


@router.message(Command("project"))
async def cmd_project(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    existing = get_user_projects(user["id"])

    if existing:
        lines = ["📁 <b>Проекты пользователя</b>"]
        for p in existing[-10:]:
            est_count = len(p.get("estimates", []))
            est_label = f", 📋 {est_count} смета" if est_count else ""
            lines.append(
                f"• <b>{p['title']}</b> — {p['project_type']}, "
                f"{p['area_m2']} м², создан {p['created_at'][:10]}{est_label}"
            )
        lines.append("\n➕ Создать новый — /newproject")
        await message.answer("\n".join(lines))
        return

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
            "🚫 Лимит по free-плану исчерпан.\n"
            f"Можно создать только <b>{limits['projects_per_month_label']}</b> проект(а) в месяц.\n"
            "Оформи paid-план для безлимита: /subscribe"
        )
        return
    await state.set_state(ProjectForm.title)
    await message.answer(
        "🏗 <b>Создание нового проекта</b>\n\n"
        "Шаг 1/4 — Введи <b>название объекта</b>:\n"
        "<i>(например: Квартира на Ленина, 34)</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ProjectForm.title)
async def step_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(ProjectForm.project_type)
    await message.answer("Шаг 2/4 — Выбери <b>тип объекта</b>:", reply_markup=TYPE_KB)


@router.message(ProjectForm.project_type)
async def step_type(message: Message, state: FSMContext) -> None:
    await state.update_data(project_type=message.text.strip())
    await state.set_state(ProjectForm.area)
    await message.answer(
        "Шаг 3/4 — Введи <b>площадь объекта</b> в м²:\n"
        "<i>(только число, например: 65)</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ProjectForm.area)
async def step_area(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".")
    try:
        area = int(float(raw))
        if area <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи корректное число площади, например: 42")
        return
    await state.update_data(area=area)
    await state.set_state(ProjectForm.notes)
    await message.answer(
        "Шаг 4/4 — Добавь <b>комментарий</b> к объекту:\n"
        "<i>(особенности, пожелания — или отправь <b>-</b> чтобы пропустить)</i>"
    )


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
        f"✅ <b>Проект создан!</b>\n\n"
        f"🏷 Название: <b>{project['title']}</b>\n"
        f"🏠 Тип: <b>{project['project_type']}</b>\n"
        f"📐 Площадь: <b>{project['area_m2']} м²</b>\n"
        f"📝 Комментарий: <b>{project['notes'] or '—'}</b>\n\n"
        "Теперь используй /estimate для подбора сметы.",
        reply_markup=ReplyKeyboardRemove(),
    )
