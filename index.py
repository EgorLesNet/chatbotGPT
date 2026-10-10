"""Bot service entry point for Vercel (FastAPI / ASGI): Telegram webhook + health check."""
import asyncio
import logging
from datetime import datetime, timezone

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, Response
from sqlalchemy import text

from app_factory import build_bot, build_dispatcher
from config import BOT_TOKEN, WEBHOOK_SECRET
from db.base import engine
from db.fsm_storage import PgStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
dp = build_dispatcher(PgStorage())

# Public health data is deliberately coarse: only per-service states, never
# configuration flags, error class names, queue sizes or any user data.
OPERATIONAL, DEGRADED, OUTAGE = "operational", "degraded", "outage"
RECENT_ERROR_SECONDS = 15 * 60


async def _check_database() -> str:
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("select 1")), timeout=5)
        return OPERATIONAL
    except Exception:
        logger.exception("Health check: database error")
        return OUTAGE


async def _check_telegram() -> str:
    if not BOT_TOKEN or not WEBHOOK_SECRET:
        return OUTAGE
    bot = build_bot()
    try:
        info = await asyncio.wait_for(bot.get_webhook_info(), timeout=5)
        if not info.url:
            logger.warning("Health check: Telegram webhook is not set")
            return OUTAGE
        last_error = info.last_error_date
        if last_error:
            if last_error.tzinfo is None:
                last_error = last_error.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - last_error).total_seconds()
            if age < RECENT_ERROR_SECONDS:
                return DEGRADED
        return OPERATIONAL
    except Exception:
        logger.exception("Health check: Telegram API error")
        return DEGRADED
    finally:
        await bot.session.close()


@app.get("/api/health")
async def health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    database, telegram = await asyncio.gather(_check_database(), _check_telegram())
    states = {"api": OPERATIONAL, "database": database, "telegram": telegram}
    if OUTAGE in states.values():
        overall = OUTAGE
    elif DEGRADED in states.values():
        overall = DEGRADED
    else:
        overall = OPERATIONAL
    return {"status": overall, "services": states}


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
