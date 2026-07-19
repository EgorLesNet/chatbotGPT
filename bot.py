import asyncio
import logging
import os
import socket

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from handlers.repair_type import router as repair_type_router
from handlers.estimate import router as estimate_router
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
    repair_type_router,
    estimate_router,
    rates_router,
    project_router,
    subscribe_router,
    voice_router,
]:
    dp.include_router(router)


def find_free_port(start_port: int, max_attempts: int = 10) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("0.0.0.0", port)) != 0:
                return port
    raise OSError(f"No free port found in range {start_port}–{start_port + max_attempts}")


async def healthcheck(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def main() -> None:
    port = find_free_port(WEBHOOK_PORT)
    if port != WEBHOOK_PORT:
        logging.warning("Port %s is busy, using port %s instead", WEBHOOK_PORT, port)

    app = web.Application()
    app.router.add_get("/health", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Healthcheck server listening on port %s", port)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
