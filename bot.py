"""Local development entry point (long polling). Production runs as a webhook: api/index.py"""
import asyncio
import logging

from aiogram.fsm.storage.memory import MemoryStorage

from app_factory import build_bot, build_dispatcher
from db.base import init_db

logging.basicConfig(level=logging.INFO)


async def main():
    await init_db()
    bot = build_bot()
    dp = build_dispatcher(MemoryStorage())
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
