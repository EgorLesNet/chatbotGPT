from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("voice"))
async def cmd_voice(message: Message) -> None:
    await message.answer(
        "🎤 Голосовой режим пока в заготовке.\n"
        "Следующий шаг: принимать voice, отправлять в STT и превращать запрос в структуру проекта."
    )
