import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from handlers.estimate import router as estimate_router
from handlers.materials import router as materials_router
from handlers.project import router as project_router
from handlers.rates import router as rates_router
from handlers.start import router as start_router
from handlers.subscribe import router as subscribe_router
from handlers.voice import router as voice_router

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

for router in [
    start_router,
    estimate_router,
    rates_router,
    project_router,
    materials_router,
    subscribe_router,
    voice_router,
]:
    dp.include_router(router)


async def healthcheck(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def main() -> None:
    app = web.Application()
    app.router.add_get("/health", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logging.info("Healthcheck server listening on port %s", WEBHOOK_PORT)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
