from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.logger import log_action
from utils.storage import ensure_user
from utils.subscription import get_plan_name, is_paid_active
from utils.keyboards import back_kb
from utils.tribute import get_tribute_pay_url

router = Router()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    user = ensure_user(message.from_user)
    user_id = user["id"]
    log_action(user_id, "subscribe_opened")

    active = is_paid_active(user)
    plan = get_plan_name(user)
    plan_icon = "💳" if active else "🆓"

    if active:
        kb = back_kb()
    else:
        pay_url = get_tribute_pay_url(user_id)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить Paid-план", url=pay_url)],
                [InlineKeyboardButton(text="← Назад", callback_data="nav:menu")],
            ]
        )

    await message.answer(
        f"💳 <b>Подписка</b>\n\n"
        f"{plan_icon} План: <b>{plan}</b>\n"
        f"Статус: <b>{'\u0430\u043a\u0442\u0438\u0432\u043d\u0430' if active else 'free'}</b>\n"
        f"Оплачено до: <b>{user.get('paid_until') or '—'}</b>\n\n"
        "🆓 <b>Free</b> — 1 проект/мес, бюджетный вариант целиком\n"
        "💳 <b>Paid</b> — безлимит проектов, все 3 варианта целиком, PDF",
        reply_markup=kb,
    )
