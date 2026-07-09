from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.storage import ensure_user, suggest_materials
from utils.subscription import get_material_options_limit

router = Router()


@router.message(Command("materials"))
async def cmd_materials(message: Message) -> None:
    user = ensure_user(message.from_user)
    limit = get_material_options_limit(user)
    variants = suggest_materials(limit=limit)

    lines = ["🧱 <b>Подбор материалов</b>"]
    for idx, item in enumerate(variants, start=1):
        lines.append(
            f"{idx}. <b>{item['name']}</b> — {item['category']}; {item['price_range']}; {item['use_case']}"
        )
    lines.append("\nДля free-плана показывается 1 вариант, для paid — до 3 вариантов.")
    await message.answer("\n".join(lines))
