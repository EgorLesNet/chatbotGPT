import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)

from utils.llm import get_estimate
from utils.storage import ensure_user, get_user_projects, create_project, save_user, get_user
from utils.subscription import is_paid_active
from utils.pdf import generate_estimate_pdf

logger = logging.getLogger(__name__)
router = Router()


class EstimateForm(StatesGroup):
    situation = State()
    new_project_title = State()
    new_project_type = State()
    new_project_area = State()


TYPE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Квартира"), KeyboardButton(text="Дом")],
        [KeyboardButton(text="Офис"), KeyboardButton(text="Коммерция")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

_ICONS = ["🟢", "🟡", "💎"]


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _format_work_line(w: dict, cur: str) -> str:
    return (
        f"   • {w['name']} — {w.get('qty', '')} {w.get('unit', '')} × {_fmt(w.get('unit_price', 0))} {cur} "
        f"= <b>{_fmt(w.get('total', 0))} {cur}</b>"
    )


def _format_material_line(m: dict, cur: str) -> str:
    brand = f" ({m['brand']})" if m.get("brand") else ""
    return (
        f"   • {m['name']}{brand} — {m.get('qty', '')} {m.get('unit', '')} × {_fmt(m.get('unit_price', 0))} {cur} "
        f"= <b>{_fmt(m.get('total', 0))} {cur}</b>"
    )


def _format_estimate(data: dict, paid: bool) -> str:
    cur = data.get("currency", "₽")
    lines = ["📋 <b>Смета ремонта</b>\n", data.get("summary", "")]
    cmin = data.get("cost_min", 0)
    cmax = data.get("cost_max", 0)
    lines.append(f"\n💰 <b>Диапазон по вариантам:</b> {_fmt(cmin)} – {_fmt(cmax)} {cur}")
    lines.append("─" * 30)

    variants = data.get("variants", [])[:3]
    if not variants:
        return "⚠️ Не удалось сформировать смету."

    # Бесплатно показываем полностью только бюджетный вариант
    eco = variants[0]
    lines.append(f"\n{_ICONS[0]} <b>{eco.get('name', 'Эконом')} — {eco.get('style', '')}</b>")
    lines.append(f"   💵 Итого: <b>{_fmt(eco.get('total', 0))} {cur}</b>")
    lines.append(
        f"   🔨 Работы: {_fmt(eco.get('total_works', 0))} {cur}  |  🧱 Материалы: {_fmt(eco.get('total_materials', 0))} {cur}"
    )

    works = eco.get("works", [])
    if works:
        lines.append("\n   🔨 <b>Работы:</b>")
        for w in works:
            lines.append(_format_work_line(w, cur))

    mats = eco.get("materials", [])
    if mats:
        lines.append("\n   🧱 <b>Материалы:</b>")
        for m in mats:
            lines.append(_format_material_line(m, cur))

    lines.append(f"\n   ✅ {eco.get('pros', '')}")
    lines.append(f"   ⚠️ {eco.get('cons', '')}")

    # Остальные — тизер. Paid может видеть их подробнее, но без точных материалов в этом экране
    for idx, v in enumerate(variants[1:], start=1):
        lines.append("")
        lines.append(f"{_ICONS[idx]} <b>{v.get('name', '')} — {v.get('style', '')}</b>")
        lines.append(f"   💵 Итого: <b>{_fmt(v.get('total', 0))} {cur}</b>")
        lines.append(
            f"   🔨 Работы: {_fmt(v.get('total_works', 0))} {cur}  |  🧱 Материалы: {_fmt(v.get('total_materials', 0))} {cur}"
        )
        works_count = len(v.get('works', []))
        mats_count = len(v.get('materials', []))
        lines.append(f"   📦 Включает: {works_count} этап(а) работ и {mats_count} позиций материалов")
        lines.append(f"   ✅ {v.get('pros', '')}")
        lines.append(f"   ⚠️ {v.get('cons', '')}")
        if paid:
            lines.append("   🔓 Подробная версия будет доступна в PDF для заказчика")
        else:
            lines.append("   🔒 Точные материалы и полная детализация — в paid-плане")

    risks = data.get("risks", "")
    if risks:
        lines.append(f"\n🔧 <b>Риски и нюансы:</b>\n{risks}")

    return "\n".join(lines)


def _after_estimate_kb(has_projects: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📂 Добавить в проект" if has_projects else "📂 Создать проект",
            callback_data="estimate:add_to_project"
        )],
        [InlineKeyboardButton(
            text="📄 PDF для заказчика",
            callback_data="estimate:pdf"
        )],
    ])


@router.message(Command("estimate"))
async def cmd_estimate(message: Message, state: FSMContext) -> None:
    await state.set_state(EstimateForm.situation)
    await message.answer(
        "📝 <b>Опиши ситуацию клиента</b>\n\n"
        "Что хочет сделать, в каком стиле, пожелания по цвету и бюджету?\n"
        "<i>Пример: Замена пола, 50 м², нужен кварцвинил, со стяжкой</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EstimateForm.situation)
async def step_situation(message: Message, state: FSMContext) -> None:
    situation = message.text.strip()
    user = ensure_user(message.from_user)
    paid = is_paid_active(user)

    await state.update_data(situation=situation, user_id=user["id"])
    wait_msg = await message.answer(
        "⏳ Анализирую ситуацию и составляю смету...\n"
        "<i>(обычно 15–60 секунд)</i>"
    )
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        estimate = await get_estimate(situation=situation, user_id=user["id"])
        text = _format_estimate(estimate, paid=paid)
        await wait_msg.delete()
        await state.update_data(last_estimate=estimate)
        await state.set_state(None)
        projects = get_user_projects(user["id"])
        kb = _after_estimate_kb(has_projects=bool(projects))
        await message.answer(text, reply_markup=kb)
    except Exception:
        logger.exception("Estimate failed")
        await wait_msg.delete()
        await message.answer("⏳ Нейросеть сейчас перегружена. Попробуй ещё раз через несколько секунд.")


@router.callback_query(F.data == "estimate:add_to_project")
async def cb_add_to_project(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    projects = get_user_projects(user["id"])
    if projects:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=p["title"], callback_data=f"estimate:proj:{p['id']}")]
            for p in projects[-5:]
        ] + [[InlineKeyboardButton(text="➕ Создать новый проект", callback_data="estimate:new_project")]])
        await call.message.answer("📂 <b>Выбери проект</b> или создай новый:", reply_markup=kb)
    else:
        await state.set_state(EstimateForm.new_project_title)
        await call.message.answer(
            "🏗 У тебя пока нет проектов. Создаём новый:\n\nШаг 1/3 — Введи <b>название объекта</b>:",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.callback_query(F.data == "estimate:new_project")
async def cb_new_project(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EstimateForm.new_project_title)
    await call.message.answer("Шаг 1/3 — Введи <b>название объекта</b>:", reply_markup=ReplyKeyboardRemove())


@router.callback_query(F.data.startswith("estimate:proj:"))
async def cb_pick_project(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    proj_id = call.data.split(":", 2)[2]
    data = await state.get_data()
    estimate = data.get("last_estimate")
    user = ensure_user(call.from_user)
    full_user = get_user(user["id"])
    project = next((p for p in full_user.get("projects", []) if p["id"] == proj_id), None)
    if not project:
        await call.message.answer("⚠️ Проект не найден.")
        return
    project.setdefault("estimates", []).append(estimate)
    save_user(full_user)
    await call.message.answer(f"✅ Смета сохранена в проект <b>{project['title']}</b>.")


@router.message(EstimateForm.new_project_title)
async def step_new_title(message: Message, state: FSMContext) -> None:
    await state.update_data(new_title=message.text.strip())
    await state.set_state(EstimateForm.new_project_type)
    await message.answer("Шаг 2/3 — Выбери <b>тип объекта</b>:", reply_markup=TYPE_KB)


@router.message(EstimateForm.new_project_type)
async def step_new_type(message: Message, state: FSMContext) -> None:
    await state.update_data(new_type=message.text.strip())
    await state.set_state(EstimateForm.new_project_area)
    await message.answer("Шаг 3/3 — Введи <b>площадь</b> в м² (например: 65):", reply_markup=ReplyKeyboardRemove())


@router.message(EstimateForm.new_project_area)
async def step_new_area(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".")
    try:
        area = int(float(raw))
        if area <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи корректное число, например: 42")
        return
    data = await state.get_data()
    estimate = data.get("last_estimate", {})
    user = ensure_user(message.from_user)
    project = create_project(
        user_id=user["id"],
        title=data["new_title"],
        project_type=data["new_type"],
        area_m2=area,
        notes="",
    )
    full_user = get_user(user["id"])
    for p in full_user.get("projects", []):
        if p["id"] == project["id"]:
            p.setdefault("estimates", []).append(estimate)
    save_user(full_user)
    await state.clear()
    await message.answer(f"✅ Проект <b>{project['title']}</b> создан, смета сохранена.", reply_markup=ReplyKeyboardRemove())


@router.callback_query(F.data == "estimate:pdf")
async def cb_pdf(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    if not is_paid_active(user):
        await call.message.answer("🔒 <b>PDF-отчёт доступен в paid-плане.</b>\nОформи подписку: /subscribe")
        return
    data = await state.get_data()
    estimate = data.get("last_estimate")
    if not estimate:
        await call.message.answer("⚠️ Данные расчёта не найдены. Сделай новый /estimate.")
        return
    try:
        pdf_path = generate_estimate_pdf(estimate)
        with open(pdf_path, "rb") as f:
            await call.message.answer_document(document=f, caption="📄 Смета для заказчика")
    except NotImplementedError:
        await call.message.answer("⏳ <b>PDF-генерация в разработке.</b>\nМы уведомим, когда будет готова.")
    except Exception:
        logger.exception("PDF generation failed")
        await call.message.answer("⚠️ Не удалось сгенерировать PDF. Попробуй позже.")
