from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from utils.storage import ensure_user, get_user_rates, save_user_rates
from utils.keyboards import rates_menu_kb, back_kb

router = Router()


class RatesForm(StatesGroup):
    add_name = State()
    add_unit = State()
    add_price = State()
    add_note = State()
    edit_pick = State()
    edit_price = State()
    delete_pick = State()


def _rates_text(rates: list[dict]) -> str:
    lines = ["💸 <b>Мои расценки</b>"]
    if rates:
        for idx, item in enumerate(rates, start=1):
            note = f" — {item['note']}" if item.get("note") else ""
            lines.append(f"{idx}. <b>{item['name']}</b>: {item['unit_price']} ₽/{item['unit']}{note}")
    else:
        lines.append("Пока нет расценок. Добавь первую!")
    lines.append("\nНажми кнопку ниже для управления расценками.")
    return "\n".join(lines)


@router.message(Command("rates"))
async def cmd_rates(message: Message) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    await message.answer(_rates_text(rates), reply_markup=rates_menu_kb())


@router.callback_query(F.data == "nav:rates")
async def cb_nav_rates(call: CallbackQuery) -> None:
    user = ensure_user(call.from_user)
    rates = get_user_rates(user["id"])
    await call.message.answer(_rates_text(rates), reply_markup=rates_menu_kb())
    await call.answer()


# ——— ADD ———

@router.callback_query(F.data == "rates:add")
async def cb_rates_add(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(RatesForm.add_name)
    await call.message.answer(
        "➕ <b>Новая расценка</b>\n\nШаг 1/3 — название работы:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("rates_add"))
async def cmd_rates_add(message: Message, state: FSMContext) -> None:
    ensure_user(message.from_user)
    await state.set_state(RatesForm.add_name)
    await message.answer("➕ <b>Новая расценка</b>\n\nШаг 1/3 — название работы:", reply_markup=ReplyKeyboardRemove())


@router.message(RatesForm.add_name)
async def rate_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(RatesForm.add_unit)
    await message.answer("Шаг 2/3 — единица измерения (m², п.m., шт):")


@router.message(RatesForm.add_unit)
async def rate_add_unit(message: Message, state: FSMContext) -> None:
    await state.update_data(unit=message.text.strip())
    await state.set_state(RatesForm.add_price)
    await message.answer("Шаг 3/3 — цена за единицу, ₽ (только число):")


@router.message(RatesForm.add_price)
async def rate_add_price(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".")
    try:
        price = int(float(raw))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи корректную цену, например: 650")
        return
    await state.update_data(price=price)
    await state.set_state(RatesForm.add_note)
    await message.answer("Комментарий (необязательно) или <b>-</b> чтобы пропустить:")


@router.message(RatesForm.add_note)
async def rate_add_note(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    note = message.text.strip()
    if note == "-":
        note = ""
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    rates.append({"name": data["name"], "unit": data["unit"], "unit_price": data["price"], "note": note})
    save_user_rates(user["id"], rates)
    await state.clear()
    await message.answer("✅ Расценка добавлена!\n\n" + _rates_text(rates), reply_markup=rates_menu_kb())


# ——— EDIT ———

@router.callback_query(F.data == "rates:edit")
async def cb_rates_edit(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    rates = get_user_rates(user["id"])
    if not rates:
        await call.message.answer("⚠️ Нет расценок. Сначала добавь.", reply_markup=rates_menu_kb())
        return
    lines = ["✏️ <b>Какую изменить?</b> Отправь номер:"]
    for idx, item in enumerate(rates, start=1):
        lines.append(f"{idx}. {item['name']} — {item['unit_price']} ₽/{item['unit']}")
    await state.set_state(RatesForm.edit_pick)
    await call.message.answer("\n".join(lines))


@router.message(Command("rates_edit"))
async def cmd_rates_edit(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    lines = ["✏️ <b>Какую расценку изменить?</b> Отправь номер:"]
    for idx, item in enumerate(rates, start=1):
        lines.append(f"{idx}. {item['name']} — {item['unit_price']} ₽/{item['unit']}")
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
        await message.answer("⚠️ Отправь корректный номер.")
        return
    await state.update_data(edit_idx=idx)
    await state.set_state(RatesForm.edit_price)
    await message.answer(f"Новая цена для <b>{rates[idx]['name']}</b> (сейчас {rates[idx]['unit_price']} ₽/{rates[idx]['unit']}):")


@router.message(RatesForm.edit_price)
async def rate_edit_price(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".")
    try:
        price = int(float(raw))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи корректную цену, например: 850")
        return
    data = await state.get_data()
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    rates[data["edit_idx"]]["unit_price"] = price
    save_user_rates(user["id"], rates)
    await state.clear()
    await message.answer("✅ Цена обновлена!\n\n" + _rates_text(rates), reply_markup=rates_menu_kb())


# ——— DELETE ———

@router.callback_query(F.data == "rates:delete")
async def cb_rates_delete(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    user = ensure_user(call.from_user)
    rates = get_user_rates(user["id"])
    if not rates:
        await call.message.answer("⚠️ Нечего удалять.", reply_markup=rates_menu_kb())
        return
    lines = ["🗑 <b>Какую удалить?</b> Отправь номер:"]
    for idx, item in enumerate(rates, start=1):
        lines.append(f"{idx}. {item['name']} — {item['unit_price']} ₽/{item['unit']}")
    await state.set_state(RatesForm.delete_pick)
    await call.message.answer("\n".join(lines))


@router.message(Command("rates_delete"))
async def cmd_rates_delete(message: Message, state: FSMContext) -> None:
    user = ensure_user(message.from_user)
    rates = get_user_rates(user["id"])
    lines = ["🗑 <b>Какую расценку удалить?</b> Отправь номер:"]
    for idx, item in enumerate(rates, start=1):
        lines.append(f"{idx}. {item['name']} — {item['unit_price']} ₽/{item['unit']}")
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
        await message.answer("⚠️ Отправь корректный номер.")
        return
    removed = rates.pop(idx)
    save_user_rates(user["id"], rates)
    await state.clear()
    await message.answer(f"✅ Удалено: <b>{removed['name']}</b>\n\n" + _rates_text(rates), reply_markup=rates_menu_kb())
