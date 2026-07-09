import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiohttp import web

from ai_client import ask_ai
from storage import get_user, increment_messages, reset_history_for_user
from tribute_webhook import handle_tribute_webhook

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DAILY_FREE_LIMIT = int(os.getenv("DAILY_FREE_LIMIT", "20"))
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    reset_history_for_user(message.from_user.id)
    await message.answer(
        "👋 Привет! Я ИИ-ассистент на базе нейросети.\n\n"
        f"🆓 Бесплатно: <b>{DAILY_FREE_LIMIT} сообщений в день</b>\n"
        "💎 Подписка: безлимит\n\n"
        "Просто напиши свой вопрос 👇\n"
        "/status — мой статус и лимит\n"
        "/reset — очистить историю диалога"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    reset_history_for_user(message.from_user.id)
    await message.answer("✅ История диалога очищена.")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    user = get_user(message.from_user.id)
    if user.get("subscribed"):
        from datetime import date
        expires = user.get("subscription_expires", "неизвестно")
        await message.answer(
            f"💎 Подписка активна — безлимитный доступ!\n"
            f"📅 Действует до: <b>{expires}</b>"
        )
    else:
        used = user.get("daily_count", 0)
        remaining = max(0, DAILY_FREE_LIMIT - used)
        await message.answer(
            f"📊 Использовано сегодня: <b>{used}/{DAILY_FREE_LIMIT}</b>\n"
            f"Осталось бесплатных: <b>{remaining}</b>"
        )


@dp.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)

    # Проверяем подписку через поле subscribed
    if not user.get("subscribed"):
        daily_count = user.get("daily_count", 0)
        if daily_count >= DAILY_FREE_LIMIT:
            await message.answer(
                f"🚫 Ты исчерпал бесплатный лимит на сегодня (<b>{DAILY_FREE_LIMIT} сообщений</b>).\n"
                "Лимит обновится завтра в полночь по МСК.\n\n"
                "💎 Оформи подписку для безлимитного доступа."
            )
            return

    history = user.get("history", [])
    history.append({"role": "user", "content": message.text})
    history = history[-10:]

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        answer, used_model = await ask_ai(history)
    except Exception:
        logging.exception("AI request failed")
        await message.answer("❌ Не удалось получить ответ, попробуй позже 🙏")
        return

    history.append({"role": "assistant", "content": answer})
    increment_messages(user_id, history)

    model_short = used_model.split("/")[-1].replace(":free", "")
    await message.answer(f"{answer}\n\n<i>🤖 {model_short}</i>")


async def on_tribute_webhook(request: web.Request) -> web.Response:
    """Точка приёма вебхуков от Tribute"""
    body = await request.read()
    signature = request.headers.get("trbt-signature", "")
    await handle_tribute_webhook(body, signature, bot)
    return web.Response(text="ok")


async def main():
    app = web.Application()
    app.router.add_post("/tribute", on_tribute_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logging.info(f"Tribute webhook listening on port {WEBHOOK_PORT}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
