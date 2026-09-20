import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from db.base import init_db
from handlers.auth import router as auth_router
from handlers.foreman.sites import router as f_sites_router
from handlers.foreman.tasks import router as f_tasks_router
from handlers.foreman.workers import router as f_workers_router
from handlers.foreman.chat import router as f_chat_router
from handlers.worker.sites import router as w_sites_router
from handlers.worker.tasks import router as w_tasks_router
from handlers.worker.chat import router as w_chat_router
from middlewares.auth import AuthMiddleware

load_dotenv()
logging.basicConfig(level=logging.INFO)


async def main():
    await init_db()

    bot = Bot(
        token=os.getenv("BOT_TOKEN", ""),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    dp.include_routers(
        auth_router,
        f_sites_router,
        f_tasks_router,
        f_workers_router,
        f_chat_router,
        w_sites_router,
        w_tasks_router,
        w_chat_router,
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
