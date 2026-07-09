import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ai_client import ask_ai
from storage import get_user, increment_messages, reset_history_for_user

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TRIBUTE_CHANNEL = os.getenv("TRIBUTE_CHANNEL", "")  # username канала Tribute, например @mychannel
DAILY_FREE_LIMIT = 20

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


async def is_subscriber(user_id: int) -> bool:
    """Проверяет, состоит ли пользователь в Tribute-канале (платная подписка)."""
    if not TRIBUTE_CHANNEL:
        return False
    try:
        member = await bot.get_chat_member(chat_id=TRIBUTE_CHANNEL, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


@dp.message(CommandStart())
async def cmd_start(message: Message):
    reset_history_for_user(message.from_user.id)
    tribute_text = f"\n💎 Безлимитный доступ — подписка Tribute: {TRIBUTE_CHANNEL}" if TRIBUTE_CHANNEL else ""
    await message.answer(
        "👋 Привет! Я ИИ-ассистент на базе нейросети.\n\n"
        f"🆓 Бесплатно: <b>{DAILY_FREE_LIMIT} сообщений в день</b>"
        f"{tribute_text}\n\n"
        "Просто напиши свой вопрос 👇\n"
        "/reset — очистить историю диалога\n"
        "/status — мой лимит сегодня"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    reset_history_for_user(message.from_user.id)
    await message.answer("✅ История диалога очищена.")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    user_id = message.from_user.id
    subscribed = await is_subscriber(user_id)
    user = get_user(user_id)
    used = user.get("daily_count", 0)
    remaining = max(0, DAILY_FREE_LIMIT - used)

    if subscribed:
        await message.answer("💎 У тебя активна платная подписка — безлимитный доступ!")
    else:
        tribute_hint = f"\n\nПодписка для безлимита: {TRIBUTE_CHANNEL}" if TRIBUTE_CHANNEL else ""
        await message.answer(
            f"📊 Использовано сегодня: <b>{used}/{DAILY_FREE_LIMIT}</b>\n"
            f"Осталось бесплатных: <b>{remaining}</b>"
            f"{tribute_hint}"
        )


@dp.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    subscribed = await is_subscriber(user_id)
    user = get_user(user_id)

    # Проверяем лимит только для бесплатных пользователей
    if not subscribed:
        daily_count = user.get("daily_count", 0)
        if daily_count >= DAILY_FREE_LIMIT:
            tribute_text = f"\n\n💎 Оформи подписку для безлимита: {TRIBUTE_CHANNEL}" if TRIBUTE_CHANNEL else ""
            await message.answer(
                f"🚫 Ты исчерпал бесплатный лимит на сегодня (<b>{DAILY_FREE_LIMIT} сообщений</b>).\n"
                f"Лимит обновится завтра в полночь по МСК."
                f"{tribute_text}"
            )
            return

    history = user.get("history", [])
    history.append({"role": "user", "content": message.text})
    history = history[-10:]  # ограничиваем контекст

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        answer, used_model = await ask_ai(history)
    except Exception:
        logging.exception("AI request failed")
        await message.answer("❌ Не удалось получить ответ от нейросети, попробуй позже 🙏")
        return

    history.append({"role": "assistant", "content": answer})
    increment_messages(user_id, history)

    model_short = used_model.split("/")[-1].replace(":free", "")
    await message.answer(f"{answer}\n\n<i>🤖 {model_short}</i>")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
