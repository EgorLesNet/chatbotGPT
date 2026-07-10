from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from utils.storage import (
    create_project, ensure_user, get_user_projects,
    get_project_by_id, update_estimate_in_project,
    delete_estimate_from_project, reset_user_month,
)
from utils.subscription import can_create_project, get_plan_limits
from utils.keyboards import back_kb

router = Router()


class ProjectForm(StatesGroup):
    title = State()
    project_type = State()
    area = State()
    notes = State()


class EstimateEditForm(StatesGroup):
    waiting_value = State()   # ждём новое значение поля


TYPE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Квартира"), KeyboardButton(text="Дом")],
        [KeyboardButton(text="Офис"), KeyboardButton(text="Коммерция")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# ─────────────────────────────────────────────
# Вспомогательные форматтеры
# ─────────────────────────────────────────────

def _fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(n)


def _projects_list_kb(projects: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"📁 {p['title']} ({len(p.get('estimates', []))} смет)",
            callback_data=f"proj:view:{p['id']}",
        )]
        for p in projects[-10:]
    ]
    rows.append([InlineKeyboardButton(text="➕ Новый проект", callback_data="project:new")])
    rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _project_detail_text(p: dict) -> str:
    lines = [
        f"📁 <b>{p['title']}</b>",
        f"🏠 {p['project_type']} · 📐 {p['area_m2']} м²",
    ]
    if p.get("notes"):
        lines.append(f"📝 {p['notes']}")
    lines.append(f"📅 Создан: {p['created_at'][:10]}")
    estimates = p.get("estimates") or []
    lines.append(f"\n📋 <b>Сметы ({len(estimates)}):</b>")
    if not estimates:
        lines.append("  — пока нет")
    else:
        for i, e in enumerate(estimates):
            cmin = _fmt(e.get("cost_min", 0))
            cmax = _fmt(e.get("cost_max", 0))
            cur = e.get("currency", "₽")
            summary_short = (e.get("summary") or "")[:60]
            lines.append(f"  {i + 1}. {summary_short or '—'} · {cmin}–{cmax} {cur}")
    return "\n".join(lines)


def _project_detail_kb(project_id: str, estimates: list) -> InlineKeyboardMarkup:
    rows = []
    for i, e in enumerate(estimates):
        label = (e.get("summary") or f"Смета {i + 1}")[:30]
        rows.append([InlineKeyboardButton(
            text=f"📋 {label}",
            callback_data=f"proj:est:{project_id}:{i}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Новая смета", callback_data="nav:estimate")])
    rows.append([InlineKeyboardButton(text="◀️ К проектам", callback_data="nav:projects")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _estimate_detail_text(e: dict, idx: int) -> str:
    cur = e.get("currency", "₽")
    lines = [
        f"📋 <b>Смета #{idx + 1}</b>",
        f"📝 {e.get('summary') or '—'}",
        f"💰 Диапазон: <b>{_fmt(e.get('cost_min', 0))}–{_fmt(e.get('cost_max', 0))} {cur}</b>",
        "",
    ]
    for v in (e.get("variants") or [])[:3]:
        lines.append(
            f"• <b>{v.get('name', '')} — {v.get('style', '')}</b>  "
            f"{_fmt(v.get('total', 0))} {cur}"
        )
        lines.append(
            f"  🔨 работы {_fmt(v.get('total_works', 0))}  "
            f"🧱 материалы {_fmt(v.get('total_materials', 0))}"
        )
    risks = e.get("risks", "")
    if risks:
        lines.append(f"\n🔧 <b>Риски:</b> {risks}")
    return "\n".join(lines)


def _estimate_detail_kb(project_id: str, idx: int) -> InlineKeyboardMarkup:
    pid = project_id
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Описание",  callback_data=f"est:edit:{pid}:{idx}:summary"),
            InlineKeyboardButton(text="✏️ Риски",     callback_data=f"est:edit:{pid}:{idx}:risks"),
        ],
        [
            InlineKeyboardButton(text="✏️ Итог Эконом",    callback_data=f"est:edit:{pid}:{idx}:v0total"),
            InlineKeyboardButton(text="✏️ Итог Оптимал",   callback_data=f"est:edit:{pid}:{idx}:v1total"),
        ],
        [
            InlineKeyboardButton(text="✏️ Итог Премиум",   callback_data=f"est:edit:{pid}:{idx}:v2total"),
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить смету", callback_data=f"est:delete:{pid}:{idx}"),
        ],
        [
            InlineKeyboardButton(text="◀️ К проекту", callback_data=f"proj:view:{pid}"),
        ],
    ])


# ─────────────────────────────────────────────
# Список проектов
# ─────────────────────────────────────────────

@router.callback_query(F.data == "nav:projects")
async def cb_nav_projects(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    reset_user_month(user["id"])
    projects = get_user_projects(user["id"])
    if projects:
        await call.message.answer(
            "📁 <b>Проекты</b> — выбери чтобы открыть:",
            reply_markup=_projects_list_kb(projects),
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать проект", callback_data="project:new")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")],
        ])
        await call.message.answer("📁 Проектов пока нет.", reply_markup=kb)


# ─────────────────────────────────────────────
# Детали проекта
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("proj:view:"))
async def cb_project_view(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    project_id = call.data.split(":", 2)[2]
    project = get_project_by_id(user["id"], project_id)
    if not project:
        await call.message.answer("⚠️ Проект не найден.")
        return
    estimates = project.get("estimates") or []
    await call.message.answer(
        _project_detail_text(project),
        reply_markup=_project_detail_kb(project_id, estimates),
    )


# ─────────────────────────────────────────────
# Детали конкретной сметы
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("proj:est:"))
async def cb_estimate_view(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    # proj:est:<project_id>:<idx>
    parts = call.data.split(":")
    project_id = parts[2]
    idx = int(parts[3])
    project = get_project_by_id(user["id"], project_id)
    if not project:
        await call.message.answer("⚠️ Проект не найден.")
        return
    estimates = project.get("estimates") or []
    if idx >= len(estimates):
        await call.message.answer("⚠️ Смета не найдена.")
        return
    e = estimates[idx]
    await call.message.answer(
        _estimate_detail_text(e, idx),
        reply_markup=_estimate_detail_kb(project_id, idx),
    )


# ─────────────────────────────────────────────
# Редактирование поля сметы
# ─────────────────────────────────────────────

_FIELD_LABELS = {
    "summary":  "описание (summary)",
    "risks":    "риски",
    "v0total":  "итог варианта Эконом (число ₽)",
    "v1total":  "итог варианта Оптимальный (число ₽)",
    "v2total":  "итог варианта Премиум (число ₽)",
}


@router.callback_query(F.data.startswith("est:edit:"))
async def cb_estimate_edit_start(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    # est:edit:<project_id>:<idx>:<field>
    parts = call.data.split(":")
    project_id = parts[2]
    idx = int(parts[3])
    field = parts[4]
    label = _FIELD_LABELS.get(field, field)
    await state.update_data(edit_project_id=project_id, edit_idx=idx, edit_field=field)
    await state.set_state(EstimateEditForm.waiting_value)
    await call.message.answer(
        f"✏️ Введи новое значение для <b>{label}</b>:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EstimateEditForm.waiting_value)
async def cb_estimate_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    project_id = data["edit_project_id"]
    idx = data["edit_idx"]
    field = data["edit_field"]
    user = ensure_user(message.from_user)
    await state.clear()

    raw = message.text.strip()

    # Поля vNtotal — патчим variant[N]["total"] и пересчитываем cost_min/cost_max
    if field in ("v0total", "v1total", "v2total"):
        try:
            new_total = int(float(raw.replace(" ", "").replace(",", ".")))
        except ValueError:
            await message.answer("⚠️ Введи целое число, например: 350000")
            return
        project = get_project_by_id(user["id"], project_id)
        if not project:
            await message.answer("⚠️ Проект не найден.")
            return
        estimates = project.get("estimates") or []
        if idx >= len(estimates):
            await message.answer("⚠️ Смета не найдена.")
            return
        e = estimates[idx]
        v_idx = int(field[1])  # 0/1/2
        variants = e.get("variants") or []
        if v_idx < len(variants):
            variants[v_idx]["total"] = new_total
        # пересчёт диапазона
        totals = [v.get("total", 0) for v in variants if v.get("total", 0) > 0]
        patch = {"variants": variants}
        if totals:
            patch["cost_min"] = min(totals)
            patch["cost_max"] = max(totals)
        ok = update_estimate_in_project(user["id"], project_id, idx, patch)
    else:
        # summary или risks — просто текст
        ok = update_estimate_in_project(user["id"], project_id, idx, {field: raw})

    if ok:
        await message.answer(
            "✅ Сохранено!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Назад к смете", callback_data=f"proj:est:{project_id}:{idx}")],
                [InlineKeyboardButton(text="📁 К проекту",    callback_data=f"proj:view:{project_id}")],
            ]),
        )
    else:
        await message.answer("⚠️ Не удалось сохранить. Попробуй снова.", reply_markup=back_kb())


# ─────────────────────────────────────────────
# Удаление сметы
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("est:delete:"))
async def cb_estimate_delete(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    # est:delete:<project_id>:<idx>
    parts = call.data.split(":")
    project_id = parts[2]
    idx = int(parts[3])
    user = ensure_user(call.from_user)
    # Запрашиваем подтверждение
    await call.message.answer(
        "🗑 Удалить эту смету? Это действие нельзя отменить.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить",  callback_data=f"est:delete_ok:{project_id}:{idx}"),
                InlineKeyboardButton(text="❌ Отмена",        callback_data=f"proj:est:{project_id}:{idx}"),
            ],
        ]),
    )


@router.callback_query(F.data.startswith("est:delete_ok:"))
async def cb_estimate_delete_ok(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    parts = call.data.split(":")
    project_id = parts[2]
    idx = int(parts[3])
    user = ensure_user(call.from_user)
    ok = delete_estimate_from_project(user["id"], project_id, idx)
    if ok:
        await call.message.answer(
            "🗑 Смета удалена.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📁 К проекту", callback_data=f"proj:view:{project_id}")],
            ]),
        )
    else:
        await call.message.answer("⚠️ Не удалось удалить.", reply_markup=back_kb())


# ─────────────────────────────────────────────
# Создание проекта
# ─────────────────────────────────────────────

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
    projects = get_user_projects(user["id"])
    if projects:
        await message.answer(
            "📁 <b>Проекты</b> — выбери чтобы открыть:",
            reply_markup=_projects_list_kb(projects),
        )
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📁 К проектам", callback_data="nav:projects")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")],
        ]),
    )
