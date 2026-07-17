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
from utils.keyboards import after_estimate_kb

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
        return "⚠️ Не удалось сформировать смету. Попробуй ещё раз или опиши задачу подробнее."

    # Эконом — полная детализация (free + paid)
    eco = variants[0]
    lines.append(f"\n{_ICONS[0]} <b>{eco.get('name', 'Эконом')} — {eco.get('style', '')}</b>")
    lines.append(f"   💵 Итого: <b>{_fmt(eco.get('total', 0))} {cur}</b>")
    lines.append(
        f"   🔨 Работы: {_fmt(eco.get('total_works', 0))} {cur}   🧱 Материалы: {_fmt(eco.get('total_materials', 0))} {cur}"
    )
    for w in eco.get("works", []):
        lines.append(_format_work_line(w, cur))
    lines.append("")
    for m in eco.get("materials", []):
        lines.append(_format_material_line(m, cur))
    lines.append(f"\n   ✅ {eco.get('pros', '')}")
    lines.append(f"   ⚠️ {eco.get('cons', '')}")

    # Оптимальный и Премиум — тизер для free, полная детализация для paid
    for idx, v in enumerate(variants[1:], start=1):
        lines.append("")
        lines.append(f"{_ICONS[idx]} <b>{v.get('name', '')} — {v.get('style', '')}</b>")
        lines.append(f"   💵 Итого: <b>{_fmt(v.get('total', 0))} {cur}</b>")
        lines.append(
            f"   🔨 {_fmt(v.get('total_works', 0))} {cur}   🧱 {_fmt(v.get('total_materials', 0))} {cur}"
        )
        n_works = len(v.get("works", []))
        n_mats = len(v.get("materials", []))
        lines.append(f"   📦 {n_works} позиций работ · {n_mats} позиций материалов")
        lines.append(f"   ✅ {v.get('pros', '')}")
        lines.append(f"   ⚠️ {v.get('cons', '')}")
        if paid:
            lines.append("   🔓 Полная детализация доступна в PDF")
        else:
            lines.append("   🔒 <i>Детализация по позициям — в paid-плане</i>")

    risks = data.get("risks", "")
    if risks:
        lines.append(f"\nℹ️ <b>Важно знать:</b> {risks}")

    return "\n".join(lines)


@router.message(Command("estimate"))
async def cmd_estimate(message: Message, state: FSMContext) -> None:
    from handlers.repair_type import repair_type_kb
    await state.clear()
    await message.answer(
        "📋 <b>Новая смета</b>\n\n"
        "Выбери тип ремонта — бот задаст правильные параметры расчёта:",
        reply_markup=repair_type_kb(),
    )


@router.message(EstimateForm.situation)
async def step_situation(message: Message, state: FSMContext) -> None:
    situation = message.text.strip()
    user = ensure_user(message.from_user)
    paid = is_paid_active(user)
    data = await state.get_data()
    repair_label = data.get("repair_label", "")
    repair_hint = data.get("repair_hint", "")
    repair_type = data.get("repair_type", "")
    enriched_situation = situation
    if repair_label:
        enriched_situation = f"[Тип ремонта: {repair_label}] {situation}"
    await state.update_data(situation=enriched_situation, user_id=user["id"])
    wait_msg = await message.answer("⏳ Считаю смету...\n<i>Обычно занимает 15–60 секунд</i>")
    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        estimate = await get_estimate(
            situation=enriched_situation,
            user_id=user["id"],
            system_hint=repair_hint,
            repair_type=repair_type,
        )
        text = _format_estimate(estimate, paid=paid)
        await wait_msg.delete()
        await state.update_data(last_estimate=estimate)
        await state.set_state(None)
        projects = get_user_projects(user["id"])
        await message.answer(text, reply_markup=after_estimate_kb(has_projects=bool(projects)))
    except Exception:
        logger.exception("Estimate failed")
        await wait_msg.delete()
        await message.answer(
            "😔 Не удалось получить ответ от нейросети. Попробуй через несколько секунд.\n"
            "Если ошибка повторяется — опиши задачу немного иначе."
        )


@router.callback_query(F.data == "estimate:add_to_project")
async def cb_add_to_project(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    projects = get_user_projects(user["id"])
    if projects:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=p["title"], callback_data=f"estimate:proj:{p['id']}")]
            for p in projects[-5:]
        ] + [
            [InlineKeyboardButton(text="➕ Создать новый проект", callback_data="estimate:new_project")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu")],
        ])
        await call.message.answer("📂 <b>В какой проект сохранить смету?</b>", reply_markup=kb)
    else:
        await state.set_state(EstimateForm.new_project_title)
        await call.message.answer(
            "📂 Проектов пока нет. Создаём первый.\n\n"
            "<b>Шаг 1 из 3</b> — название объекта (например: Квартира Иванова, ул. Ленина 5):",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.callback_query(F.data == "estimate:new_project")
async def cb_new_project(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EstimateForm.new_project_title)
    await call.message.answer(
        "<b>Шаг 1 из 3</b> — название объекта (например: Квартира Иванова, ул. Ленина 5):",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.callback_query(F.data.startswith("estimate:proj:"))
async def cb_pick_project(call: CallbackQuery, state: FSMContext) -> None:
    from utils.keyboards import back_kb
    await call.answer()
    proj_id = call.data.split(":", 2)[2]
    data = await state.get_data()
    estimate = data.get("last_estimate")
    user = ensure_user(call.from_user)
    full_user = get_user(user["id"])
    project = next((p for p in full_user.get("projects", []) if p["id"] == proj_id), None)
    if not project:
        await call.message.answer("⚠️ Проект не найден. Попробуй выбрать снова.")
        return
    project.setdefault("estimates", []).append(estimate)
    save_user(full_user)
    await call.message.answer(
        f"✅ Смета сохранена в проект <b>{project['title']}</b>.",
        reply_markup=back_kb(),
    )


@router.message(EstimateForm.new_project_title)
async def step_new_title(message: Message, state: FSMContext) -> None:
    await state.update_data(new_title=message.text.strip())
    await state.set_state(EstimateForm.new_project_type)
    await message.answer("<b>Шаг 2 из 3</b> — тип объекта:", reply_markup=TYPE_KB)


@router.message(EstimateForm.new_project_type)
async def step_new_type(message: Message, state: FSMContext) -> None:
    await state.update_data(new_type=message.text.strip())
    await state.set_state(EstimateForm.new_project_area)
    await message.answer("<b>Шаг 3 из 3</b> — общая площадь объекта в м²:", reply_markup=ReplyKeyboardRemove())


@router.message(EstimateForm.new_project_area)
async def step_new_area(message: Message, state: FSMContext) -> None:
    from utils.keyboards import back_kb
    raw = message.text.strip().replace(",", ".")
    try:
        area = int(float(raw))
        if area <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи число, например: 42")
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
    await message.answer(
        f"✅ Проект <b>{project['title']}</b> создан, смета сохранена.",
        reply_markup=back_kb(),
    )


@router.callback_query(F.data == "estimate:pdf")
async def cb_pdf(call: CallbackQuery, state: FSMContext) -> None:
    from utils.keyboards import back_kb
    await call.answer()
    user = ensure_user(call.from_user)
    if not is_paid_active(user):
        await call.message.answer(
            "🔒 PDF доступен в paid-плане.\nПерейди в раздел Подписка, чтобы подключить.",
            reply_markup=back_kb(),
        )
        return
    data = await state.get_data()
    estimate = data.get("last_estimate")
    if not estimate:
        await call.message.answer(
            "⚠️ Смета не найдена. Сначала сформируй смету через раздел 📋 Смета.",
            reply_markup=back_kb(),
        )
        return
    try:
        pdf_path = generate_estimate_pdf(estimate)
        with open(pdf_path, "rb") as f:
            await call.message.answer_document(document=f, caption="📄 Смета для заказчика")
    except NotImplementedError:
        await call.message.answer(
            "⏳ Выгрузка PDF пока в разработке. Уведомим, когда появится.",
            reply_markup=back_kb(),
        )
    except Exception:
        logger.exception("PDF generation failed")
        await call.message.answer("⚠️ Не удалось создать PDF. Попробуй позже.", reply_markup=back_kb())
