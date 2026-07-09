from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.storage import ensure_user
from utils.subscription import get_plan_name, is_paid_active

router = Router()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    user = ensure_user(message.from_user)
    active = is_paid_active(user)
    plan = get_plan_name(user)
    await message.answer(
        "💳 <b>Подписка</b>\n\n"
        f"План: <b>{plan}</b>\n"
        f"Статус: <b>{'активна' if active else 'free'}</b>\n"
        f"paid_until: <b>{user.get('paid_until') or '—'}</b>\n\n"
        "Логика тарифа:\n"
        "• Free — 1 проект в месяц и 1 вариант материалов\n"
        "• Paid — безлимит по проектам и 3 варианта материалов\n\n"
        "Оплату можно подключить следующей итерацией через вебхук провайдера."
    )
