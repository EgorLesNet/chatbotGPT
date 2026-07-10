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
from utils.subscription import is_paid_active, get_material_options_limit
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


def _variant_icon(idx: int) -> str:
    return ["🟢", "🟡", "💎"][idx] if idx < 3 else "•"


def _format_estimate(data: dict, paid: bool) -> str:
    lines = []
    summary = data.get("summary", "")
    cost_min = data.get("cost_min", 0)
    cost_max = data.get("cost_max", 0)
    currency = data.get("currency", "₽")
    risks = data.get("risks", "")

    lines.append("📋 <b>Оценка ремонта</b>\n")
    lines.append(f"{summary}\n")
    try:
        cost_str = f"{int(cost_min):,} – {int(cost_max):,} {currency}".replace(",", " ")
    except (TypeError, ValueError):
        cost_str = f"{cost_min} – {cost_max} {currency}"
    lines.append(f"💰 <b>Примерная стоимость:</b> {cost_str}\n")

    variants = data.get("variants", [])[:3]
    lines.append("─" * 28)
    mat_count = 3 if paid else 1
    for idx, v in enumerate(variants):
        icon = _variant_icon(idx)
        lines.append(f"\n{icon} <b>{v.get('name', '')}</b> — {v.get('style', '')}")
        lines.append(f"   💴 {v.get('budget', '')}")
        mats = v.get("materials", [])[:mat_count]
        for mat in mats:
            note = f" ({mat.get('note', '')}" + ")" if mat.get("note") else ""
            lines.append(f"   • {mat.get('name', '')} — {mat.get('price', '')}{note}")
        if not paid and len(v.get("materials", [])) > 1:
            lines.append("   🔒 <i>+ещё материалы в paid-плане</i>")
        lines.append(f"   ✅ {v.get('pros', '')}")
        lines.append(f"   ⚠️ {v.get('cons', '')}")

    if risks:
        lines.append(f"\n🔧 <b>Риски и нюансы:</b>\n{risks}")

    return "\n".join(lines)


def _after_estimate_kb(has_projects: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="📂 Добавить в проект" if has_projects else "📂 Создать проект",
                callback_data="estimate:add_to_project",
            )
        ],
        [
            InlineKeyboardButton(
                text="📄 PDF для заказчика",
                callback_data="estimate:pdf",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("estimate"))
async def cmd_estimate(message: Message, state: FSMContext) -> None:
    await state.set_state(EstimateForm.situation)
    await message.answer(
        "📝 <b>Опиши ситуацию клиента</b>\n\n"
        "Что хочет сделать, в каком стиле, пожелания по цвету и бюджету?\n"
        "<i>Пример: Хочет покрасить стены в светлые тона, бюджет до 60 тыс, квартира 45 м², современный стиль</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EstimateForm.situation)
async def step_situation(message: Message, state: FSMContext) -> None:
    situation = message.text.strip()
    user = ensure_user(message.from_user)
    paid = is_paid_active(user)

    await state.update_data(situation=situation, user_id=user["id"])

    wait_msg = await message.answer(
        "⏳ Анализирую ситуацию и подбираю варианты...\n"
        "<i>(обычно 10–60 секунд)</i>"
    )
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        estimate = await get_estimate(situation=situation)
        text = _format_estimate(estimate, paid=paid)
        await wait_msg.delete()

        # Сохраняем estimate в state для callback-обработчиков
        await state.update_data(last_estimate=estimate)
        await state.set_state(None)

        projects = get_user_projects(user["id"])
        kb = _after_estimate_kb(has_projects=bool(projects))
        await message.answer(text, reply_markup=kb)

    except Exception:
        logger.exception("Estimate failed")
        await wait_msg.delete()
        await message.answer(
            "⏳ Нейросеть сейчас перегружена. Попробуй ещё раз через несколько секунд."
        )


# ——— callback: Добавить / Создать проект ———

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
            [InlineKeyboardButton(text="➕ Создать новый проект", callback_data="estimate:new_project")]
        ])
        await call.message.answer("📂 <b>Выбери проект</b> или создай новый:", reply_markup=kb)
    else:
        await call.message.answer("🏗 У тебя пока нет проектов. Создаём новый:")
        await state.set_state(EstimateForm.new_project_title)
        await call.message.answer(
            "Шаг 1/3 — Введи <b>название объекта</b>:\n"
            "<i>(например: Квартира на Ленина, 34)</i>",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.callback_query(F.data == "estimate:new_project")
async def cb_new_project(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EstimateForm.new_project_title)
    await call.message.answer(
        "Шаг 1/3 — Введи <b>название объекта</b>:\n"
        "<i>(например: Квартира на Ленина, 34)</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.callback_query(F.data.startswith("estimate:proj:"))
async def cb_pick_project(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    proj_id = call.data.split(":", 2)[2]
    data = await state.get_data()
    estimate = data.get("last_estimate")
    user = ensure_user(call.from_user)

    # Находим проект и добавляем смету
    full_user = get_user(user["id"])
    project = next((p for p in full_user.get("projects", []) if p["id"] == proj_id), None)
    if not project:
        await call.message.answer("⚠️ Проект не найден.")
        return

    project.setdefault("estimates", []).append(estimate)
    save_user(full_user)
    await call.message.answer(
        f"✅ Смета сохранена в проект <b>{project['title']}</b>."
    )


# ——— Создание проекта из estimate-флоу ———

@router.message(EstimateForm.new_project_title)
async def step_new_title(message: Message, state: FSMContext) -> None:
    await state.update_data(new_title=message.text.strip())
    await state.set_state(EstimateForm.new_project_type)
    await message.answer("Шаг 2/3 — Выбери <b>тип объекта</b>:", reply_markup=TYPE_KB)


@router.message(EstimateForm.new_project_type)
async def step_new_type(message: Message, state: FSMContext) -> None:
    await state.update_data(new_type=message.text.strip())
    await state.set_state(EstimateForm.new_project_area)
    await message.answer(
        "Шаг 3/3 — Введи <b>площадь</b> в м² (только число, например: 65):",
        reply_markup=ReplyKeyboardRemove(),
    )


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
    # Добавляем смету в проект
    full_user = get_user(user["id"])
    for p in full_user.get("projects", []):
        if p["id"] == project["id"]:
            p.setdefault("estimates", []).append(estimate)
    save_user(full_user)

    await state.clear()
    await message.answer(
        f"✅ Проект <b>{project['title']}</b> создан, смета сохранена.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ——— callback: PDF ———

@router.callback_query(F.data == "estimate:pdf")
async def cb_pdf(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    paid = is_paid_active(user)

    if not paid:
        await call.message.answer(
            "🔒 <b>PDF-отчёт доступен в paid-плане.</b>\n"
            "Оформи подписку: /subscribe"
        )
        return

    data = await state.get_data()
    estimate = data.get("last_estimate")
    if not estimate:
        await call.message.answer("⚠️ Данные расчёта не найдены. Сделай новый /estimate.")
        return

    try:
        pdf_path = generate_estimate_pdf(estimate)
        with open(pdf_path, "rb") as f:
            await call.message.answer_document(
                document=f,
                caption="📄 Смета для заказчика",
            )
    except NotImplementedError:
        await call.message.answer(
            "⏳ <b>PDF-генерация в разработке.</b>\n"
            "Мы уведомим, когда она будет готова. Смета сохранена в твоём аккаунте."
        )
    except Exception:
        logger.exception("PDF generation failed")
        await call.message.answer("⚠️ Не удалось сгенерировать PDF. Попробуй позже.")
