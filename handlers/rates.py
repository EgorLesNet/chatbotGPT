from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove

from utils.storage import ensure_user, get_user_rates, save_user_rates

router = Router()


class RatesForm(StatesGroup):
    add_name = State()
    add_unit = State()
    add_price = State()
    add_note = State()
    edit_pick = State()
    edit_price = State()
    delete_pick = State()


def _format_rates(rates: list[dict]) -> str:
    lines = ["💸 <b>Мои расценки</b>"]
    for idx, item in enumerate(rates, start=1):
        lines.append(
            f"{idx}. <b>{item['name']}</b>: {item['unit_price']} ₽/{item['unit']} — {item.get('note', '')}"
        )
    lines.append(
        "\nКоманды:\n"
        "/rates_add — добавить расценку\n"
        "/rates_edit — изменить цену\n"
        "/rates_delete — удалить расценку"
    )
    return "\n".join(lines)


@router.message(Command("rates"))
async def cmd_rates(message: Message) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    await message.answer(_format_rates(rates))


@router.message(Command("rates_add"))
async def cmd_rates_add(message: Message, state: FSMContext) -> None:
    ensure_user(message.from_user)
    await state.set_state(RatesForm.add_name)
    await message.answer("Введите название работы:", reply_markup=ReplyKeyboardRemove())


@router.message(RatesForm.add_name)
async def rate_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(RatesForm.add_unit)
    await message.answer("Введите единицу измерения (например: м², п.м., шт):")


@router.message(RatesForm.add_unit)
async def rate_add_unit(message: Message, state: FSMContext) -> None:
    await state.update_data(unit=message.text.strip())
    await state.set_state(RatesForm.add_price)
    await message.answer("Введите цену за единицу (только число):")


@router.message(RatesForm.add_price)
async def rate_add_price(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".")
    try:
        price = int(float(raw))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректную цену, например: 650")
        return
    await state.update_data(price=price)
    await state.set_state(RatesForm.add_note)
    await message.answer("Введите комментарий или '-' чтобы пропустить:")


@router.message(RatesForm.add_note)
async def rate_add_note(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    note = message.text.strip()
    if note == "-":
        note = ""
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    rates.append({
        "name": data["name"],
        "unit": data["unit"],
        "unit_price": data["price"],
        "note": note,
    })
    save_user_rates(user["id"], rates)
    await state.clear()
    await message.answer("✅ Расценка добавлена.\n\n" + _format_rates(rates))


@router.message(Command("rates_edit"))
async def cmd_rates_edit(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    lines = ["✏️ <b>Какую расценку изменить?</b>"]
    for idx, item in enumerate(rates, start=1):
        lines.append(f"{idx}. {item['name']} — {item['unit_price']} ₽/{item['unit']}")
    lines.append("\nОтправь номер позиции.")
    await state.set_state(RatesForm.edit_pick)
    await message.answer("\n".join(lines), reply_markup=ReplyKeyboardRemove())


@router.message(RatesForm.edit_pick)
async def rate_edit_pick(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    try:
        idx = int(message.text.strip()) - 1
        if idx < 0 or idx >= len(rates):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Отправь корректный номер позиции.")
        return
    await state.update_data(edit_idx=idx)
    await state.set_state(RatesForm.edit_price)
    await message.answer("Введите новую цену за единицу:")


@router.message(RatesForm.edit_price)
async def rate_edit_price(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".")
    try:
        price = int(float(raw))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректную цену, например: 850")
        return
    data = await state.get_data()
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    rates[data["edit_idx"]]["unit_price"] = price
    save_user_rates(user["id"], rates)
    await state.clear()
    await message.answer("✅ Расценка обновлена.\n\n" + _format_rates(rates))


@router.message(Command("rates_delete"))
async def cmd_rates_delete(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    lines = ["🗑 <b>Какую расценку удалить?</b>"]
    for idx, item in enumerate(rates, start=1):
        lines.append(f"{idx}. {item['name']} — {item['unit_price']} ₽/{item['unit']}")
    lines.append("\nОтправь номер позиции.")
    await state.set_state(RatesForm.delete_pick)
    await message.answer("\n".join(lines), reply_markup=ReplyKeyboardRemove())


@router.message(RatesForm.delete_pick)
async def rate_delete_pick(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    try:
        idx = int(message.text.strip()) - 1
        if idx < 0 or idx >= len(rates):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Отправь корректный номер позиции.")
        return
    removed = rates.pop(idx)
    save_user_rates(user["id"], rates)
    await state.clear()
    await message.answer(f"✅ Удалено: <b>{removed['name']}</b>\n\n" + _format_rates(rates))
