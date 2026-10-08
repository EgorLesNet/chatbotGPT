"""Vercel entry point: Telegram webhook for the bot (FastAPI / ASGI)."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram.types import Update  # noqa: E402
from fastapi import FastAPI, Header, HTTPException, Request  # noqa: E402

from app_factory import build_bot, build_dispatcher  # noqa: E402
from config import WEBHOOK_SECRET  # noqa: E402
from db.fsm_storage import PgStorage  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
dp = build_dispatcher(PgStorage())


@app.get("/")
async def health():
    return {"status": "ok"}


@app.post("/api/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not WEBHOOK_SECRET or x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")

    payload = await request.json()
    bot = build_bot()
    try:
        update = Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        # Always answer 200, otherwise Telegram keeps re-sending the same update
        logger.exception("Failed to process update")
    finally:
        await bot.session.close()
    return {"ok": True}
