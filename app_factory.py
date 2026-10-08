from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage

from config import BOT_TOKEN
from handlers.common_back import router as back_router
from handlers.link import router as link_router
from handlers.auth import router as auth_router
from handlers.settings import router as settings_router
from handlers.foreman.sites import router as f_sites_router
from handlers.foreman.tasks import router as f_tasks_router
from handlers.foreman.workers import router as f_workers_router
from handlers.foreman.chat import router as f_chat_router
from handlers.worker.sites import router as w_sites_router
from handlers.worker.tasks import router as w_tasks_router
from handlers.worker.chat import router as w_chat_router
from middlewares.auth import AuthMiddleware


def build_bot() -> Bot:
    return Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def build_dispatcher(storage: BaseStorage) -> Dispatcher:
    """Call once per process: routers can be attached to only one dispatcher."""
    dp = Dispatcher(storage=storage)
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_routers(
        back_router,
        link_router,
        auth_router,
        settings_router,
        f_sites_router,
        f_tasks_router,
        f_workers_router,
        f_chat_router,
        w_sites_router,
        w_tasks_router,
        w_chat_router,
    )
    return dp
