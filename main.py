import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ai_client import ask_ai, reset_history

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# user_id -> history list
user_histories: dict[int, list[dict]] = {}


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_histories[message.from_user.id] = []
    await message.answer(
        "Привет! Я бот-помощник на базе бесплатных нейросетей.\n"
        "Просто напиши вопрос, и я отвечу.\n"
        "/reset — очистить историю диалога"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    user_histories[message.from_user.id] = []
    await message.answer("Контекст диалога очищен.")


@dp.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    history = user_histories.setdefault(user_id, [])

    history.append({"role": "user", "content": message.text})
    # ограничиваем историю, чтобы не выйти за лимит токенов бесплатных моделей
    history = history[-10:]

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        answer, used_model = await ask_ai(history)
    except Exception as e:
        logging.exception("AI request failed")
        await message.answer("Не получилось получить ответ от нейросети, попробуй позже 🙏")
        return

    history.append({"role": "assistant", "content": answer})
    user_histories[user_id] = history

    await message.answer(f"{answer}\n\n<i>модель: {used_model}</i>")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
