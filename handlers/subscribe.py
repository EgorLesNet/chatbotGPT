from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.storage import ensure_user
from utils.subscription import get_plan_name, is_paid_active
from utils.keyboards import back_kb

router = Router()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    user = ensure_user(message.from_user)
    active = is_paid_active(user)
    plan = get_plan_name(user)
    plan_icon = "💳" if active else "🆓"
    await message.answer(
        f"💳 <b>Подписка</b>\n\n"
        f"{plan_icon} План: <b>{plan}</b>\n"
        f"Статус: <b>{'\u0430\u043a\u0442\u0438\u0432\u043dа' if active else 'free'}</b>\n"
        f"Оплачено до: <b>{user.get('paid_until') or '—'}</b>\n\n"
        "🆓 <b>Free</b> — 1 проект/мес, бюджетный вариант целиком\n"
        "💳 <b>Paid</b> — безлимит проектов, все 3 варианта целиком, PDF",
        reply_markup=back_kb(),
    )
