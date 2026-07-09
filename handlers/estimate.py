import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from utils.llm import get_estimate
from utils.storage import ensure_user, get_user_projects
from utils.subscription import get_material_options_limit

logger = logging.getLogger(__name__)
router = Router()


class EstimateForm(StatesGroup):
    choose_project = State()
    situation = State()


def _variant_icon(idx: int) -> str:
    return ["💚", "💛", "💎"][idx] if idx < 3 else "•"


def _format_estimate(data: dict, limit: int) -> str:
    lines = []
    summary = data.get("summary", "")
    cost_min = data.get("cost_min", 0)
    cost_max = data.get("cost_max", 0)
    currency = data.get("currency", "₽")
    risks = data.get("risks", "")

    lines.append(f"📋 <b>Оценка ремонта</b>\n")
    lines.append(f"{summary}\n")
    try:
        cost_str = f"{int(cost_min):,} – {int(cost_max):,} {currency}".replace(",", " ")
    except (TypeError, ValueError):
        cost_str = f"{cost_min} – {cost_max} {currency}"
    lines.append(f"💰 <b>Примерная стоимость:</b> {cost_str}\n")

    variants = data.get("variants", [])[:limit]
    lines.append(f"\n🧱 <b>Варианты материалов</b> (показано {len(variants)} из 3):")
    for idx, v in enumerate(variants):
        icon = _variant_icon(idx)
        lines.append(f"\n{icon} <b>{v['name']}</b> — {v.get('style', '')}")
        lines.append(f"   Бюджет: {v.get('budget', '')}")
        for mat in v.get("materials", []):
            lines.append(f"   • {mat['name']} — {mat['price']} ({mat.get('note', '')})")
        lines.append(f"   ✅ {v.get('pros', '')}")
        lines.append(f"   ⚠️ {v.get('cons', '')}")

    if risks:
        lines.append(f"\n🔧 <b>Риски и нюансы:</b>\n{risks}")
    if limit < 3:
        lines.append("\n🔒 <i>Ещё варианты — в paid-плане (/subscribe)</i>")
    return "\n".join(lines)


@router.message(Command("estimate"))
async def cmd_estimate(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    projects = get_user_projects(user["id"])

    if projects:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=p["title"])] for p in projects[-5:]]
            + [[KeyboardButton(text="Без привязки к проекту")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await state.set_state(EstimateForm.choose_project)
        await state.update_data(projects={p["title"]: p for p in projects})
        await message.answer(
            "📂 <b>К какому проекту привязать оценку?</b>\n"
            "Выбери из списка или нажми 'Без привязки':",
            reply_markup=kb,
        )
    else:
        await state.set_state(EstimateForm.situation)
        await state.update_data(project=None)
        await message.answer(
            "📝 <b>Опиши ситуацию клиента</b>\n\n"
            "Что хочет сделать, в каком стиле, пожелания по цвету и бюджету?\n"
            "<i>Пример: Хочет покрасить стены в светлые тона, бюджет до 60 тыс, квартира 45 м², современный стиль</i>",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.message(EstimateForm.choose_project)
async def step_choose_project(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    projects_map = data.get("projects", {})
    chosen = message.text.strip()
    project = projects_map.get(chosen)
    await state.update_data(project=project)
    await state.set_state(EstimateForm.situation)
    await message.answer(
        "📝 <b>Опиши ситуацию клиента</b>\n\n"
        "Что хочет сделать, в каком стиле, пожелания по цвету и бюджету?\n"
        "<i>Пример: Хочет покрасить стены в светлые тона, бюджет до 60 тыс, квартира 45 м², современный стиль</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EstimateForm.situation)
async def step_situation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    situation = message.text.strip()
    project = data.get("project")
    user = ensure_user(message.from_user)
    limit = get_material_options_limit(user)

    await state.clear()
    wait_msg = await message.answer(
        "⏳ Анализирую ситуацию и подбираю варианты...\n"
        "<i>(обычно 10–30 секунд, зависит от нагрузки нейросети)</i>"
    )
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        estimate = await get_estimate(situation=situation, project=project)
        text = _format_estimate(estimate, limit=limit)
        await wait_msg.delete()
        await message.answer(text)

    except TimeoutError:
        await wait_msg.delete()
        await message.answer(
            "⏰ <b>Нейросеть не ответила</b> — сервер перегружен.\n\n"
            "Попробуй ещё раз через несколько секунд.\n"
            "Если ошибка повторяется — попробуй другую модель в .env:\n"
            "<code>OPENROUTER_MODEL=google/gemma-3-12b-it:free</code>"
        )
    except ValueError:
        await wait_msg.delete()
        await message.answer(
            "⚠️ Модель вернула некорректный ответ. Попробуй ещё раз или смени модель:\n"
            "<code>OPENROUTER_MODEL=google/gemma-3-12b-it:free</code>"
        )
    except Exception:
        logger.exception("Estimate failed unexpectedly")
        await wait_msg.delete()
        await message.answer(
            "❌ Не удалось получить оценку. Проверь /status или попробуй позже."
        )
