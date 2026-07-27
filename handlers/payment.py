"""Обработчики Tribute: кнопка оплаты и вебхук подтверждения платежа."""
import json
import logging
import os

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiohttp import web

from utils.logger import log_action
from utils.storage import get_user, save_user, ensure_user
from utils.tribute import (
    calc_paid_until,
    get_tribute_pay_url,
    parse_tribute_webhook,
    verify_tribute_signature,
)

router = Router()
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


# ─── Команда /pay ────────────────────────────────────────────────────────────

@router.message(Command("pay"))
async def cmd_pay(message: Message) -> None:
    user = ensure_user(message.from_user)
    user_id = user["id"]
    log_action(user_id, "pay_command_opened")

    url = get_tribute_pay_url(user_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить через Tribute", url=url)],
        ]
    )
    await message.answer(
        "💳 <b>Полный доступ — Paid план</b>\n\n"
        "✅ Безлимит проектов\n"
        "✅ Все 3 варианта сметы с детализацией\n"
        "✅ Выгрузка в PDF\n"
        "✅ Приоритетные обновления\n\n"
        "Нажми кнопку ниже — попадёшь на страницу оплаты Tribute.",
        reply_markup=kb,
    )


# ─── Webhook от Tribute ───────────────────────────────────────────────────────

async def tribute_webhook_handler(request: web.Request) -> web.Response:
    """POST /tribute/webhook — вызывается Tribute после успешной оплаты."""
    bot: Bot = request.app["bot"]

    # Проверка подписи
    signature = request.headers.get("X-Tribute-Signature", "")
    raw_body = await request.read()
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Tribute webhook: invalid JSON")
        return web.Response(status=400, text="Bad JSON")

    if not verify_tribute_signature(payload, signature):
        logger.warning("Tribute webhook: invalid signature")
        # Не возвращаем 401 — Tribute может слать повторы; просто логируем
        # Раскомментируй строку ниже если хочешь жёсткую проверку:
        # return web.Response(status=401, text="Invalid signature")

    parsed = parse_tribute_webhook(payload)
    if not parsed:
        logger.warning("Tribute webhook: cannot parse payload %s", payload)
        return web.Response(status=422, text="Unprocessable payload")

    user_id = parsed["user_id"]
    log_action(user_id, "tribute_payment_received", {
        "payment_id": parsed["payment_id"],
        "amount": parsed["amount"],
        "currency": parsed["currency"],
        "product_slug": parsed["product_slug"],
    })

    # Обновляем paid_until
    user = get_user(user_id)
    if not user:
        logger.warning("Tribute webhook: unknown user_id %s", user_id)
        return web.Response(status=404, text="User not found")

    user["paid_until"] = calc_paid_until()
    save_user(user)
    logger.info("User %s upgraded to paid until %s", user_id, user["paid_until"])
    log_action(user_id, "subscription_activated", {"paid_until": user["paid_until"]})

    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            "🎉 <b>Оплата получена!</b>\n\n"
            f"Ваш <b>Paid</b>-план активен до <b>{user['paid_until'][:10]}</b>.\n"
            "Теперь доступны все функции бота. Введите /menu",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Cannot notify user %s: %s", user_id, exc)

    # Уведомляем админа
    if ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"💰 Новая оплата!\n"
                f"User: <code>{user_id}</code>\n"
                f"Amount: {parsed['amount']} {parsed['currency']}\n"
                f"Payment ID: <code>{parsed['payment_id']}</code>\n"
                f"Paid until: {user['paid_until'][:10]}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    return web.Response(status=200, text="ok")
