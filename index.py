"""Bot service entry point for Vercel (FastAPI / ASGI): Telegram webhook + health check."""
import logging

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from sqlalchemy import text

from app_factory import build_bot, build_dispatcher
from config import BOT_TOKEN, WEBHOOK_SECRET
from db.base import engine
from db.fsm_storage import PgStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
dp = build_dispatcher(PgStorage())


@app.get("/api/health")
async def health():
    db = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception as exc:  # report only the error class, never secrets
        logger.exception("Health check: database error")
        db = f"error: {type(exc).__name__}"
    return {
        "status": "ok",
        "bot_token_set": bool(BOT_TOKEN),
        "webhook_secret_set": bool(WEBHOOK_SECRET),
        "database": db,
    }


@app.post("/api/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not WEBHOOK_SECRET or x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        logger.warning("Webhook rejected: bad or missing secret token")
        raise HTTPException(status_code=403, detail="forbidden")

    payload = await request.json()
    bot = build_bot()
    try:
        update = Update.model_validate(payload, context={"bot": bot})
        logger.info("Update %s received", payload.get("update_id"))
        await dp.feed_update(bot, update)
    except Exception:
        # Always answer 200, otherwise Telegram keeps re-sending the same update
        logger.exception("Failed to process update")
    finally:
        await bot.session.close()
    return {"ok": True}
