from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.storage import ensure_user, list_rate_presets

router = Router()


@router.message(Command("rates"))
async def cmd_rates(message: Message) -> None:
    ensure_user(message.from_user)
    presets = list_rate_presets()
    lines = ["💸 <b>Ориентиры по расценкам</b>"]
    for item in presets:
        lines.append(
            f"• <b>{item['name']}</b>: {item['unit_price']} ₽/{item['unit']} — {item['note']}"
        )
    lines.append("\nЭто стартовые ориентиры для быстрого расчёта, не финальная смета.")
    await message.answer("\n".join(lines))
