"""Tribute: кнопка оплаты + ручная активация подписки администратором."""
import logging
import os
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.logger import log_action
from utils.storage import get_user, save_user, ensure_user
from utils.tribute import calc_paid_until, get_tribute_pay_url

router = Router()
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


# ─── /pay — пользователь открывает страницу оплаты ───────────────────────────

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
        "После оплаты пришли в бот команду /paid — я уведомлю администратора.\n"
        "Доступ активируется вручную в течение нескольких минут.",
        reply_markup=kb,
    )


# ─── /paid — пользователь сообщает об оплате ─────────────────────────────────

@router.message(Command("paid"))
async def cmd_paid(message: Message) -> None:
    """Пользователь нажал после оплаты — бот уведомляет админа."""
    user = ensure_user(message.from_user)
    user_id = user["id"]
    username = user.get("username") or user.get("full_name") or str(user_id)
    log_action(user_id, "paid_notification_sent")

    await message.answer(
        "✅ Заявка отправлена! Администратор активирует доступ в течение нескольких минут."
    )

    if ADMIN_ID:
        try:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"✅ Активировать {user_id}",
                            callback_data=f"admin:activate:{user_id}",
                        )
                    ]
                ]
            )
            await message.bot.send_message(
                ADMIN_ID,
                f"💰 <b>Новая оплата!</b>\n\n"
                f"User: <code>{user_id}</code> (@{username})\n"
                f"Нажми кнопку ниже для активации подписки:",
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as exc:
            logger.warning("Cannot notify admin: %s", exc)
    else:
        logger.warning("ADMIN_TELEGRAM_ID не задан — уведомление не отправлено")


# ─── /activate <user_id> [days] — ручная активация администратором ────────────

@router.message(Command("activate"))
async def cmd_activate(message: Message) -> None:
    """Только для администратора. Использование: /activate 123456789 [30]"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return

    args = (message.text or "").split()[1:]
    if not args:
        await message.answer("Использование: /activate <user_id> [дней]\nПример: /activate 123456789 30")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await message.answer("❌ Некорректный user_id.")
        return

    days = 30
    if len(args) >= 2:
        try:
            days = int(args[1])
        except ValueError:
            pass

    user = get_user(target_id)
    if not user:
        await message.answer(f"❌ Пользователь {target_id} не найден в базе.")
        return

    paid_until = calc_paid_until(days)
    user["paid_until"] = paid_until
    save_user(user)
    log_action(target_id, "subscription_activated_manual", {
        "by_admin": message.from_user.id,
        "paid_until": paid_until,
        "days": days,
    })

    await message.answer(
        f"✅ Подписка активирована!\n"
        f"User: <code>{target_id}</code>\n"
        f"До: <b>{paid_until[:10]}</b>",
        parse_mode="HTML",
    )

    try:
        await message.bot.send_message(
            target_id,
            "🎉 <b>Доступ активирован!</b>\n\n"
            f"Ваш <b>Paid</b>-план активен до <b>{paid_until[:10]}</b>.\n"
            "Теперь доступны все функции. Введите /menu",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Cannot notify user %s: %s", target_id, exc)


# ─── Callback кнопка «Активировать» в сообщении админу ───────────────────────

from aiogram import F
from aiogram.types import CallbackQuery


@router.callback_query(F.data.startswith("admin:activate:"))
async def cb_admin_activate(call: CallbackQuery) -> None:
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Нет доступа.", show_alert=True)
        return

    target_id = int(call.data.split(":")[2])
    user = get_user(target_id)
    if not user:
        await call.answer(f"❌ Пользователь {target_id} не найден.", show_alert=True)
        return

    paid_until = calc_paid_until(30)
    user["paid_until"] = paid_until
    save_user(user)
    log_action(target_id, "subscription_activated_manual", {
        "by_admin": call.from_user.id,
        "paid_until": paid_until,
        "days": 30,
    })

    await call.message.edit_text(
        call.message.text + f"\n\n✅ <b>Активировано до {paid_until[:10]}</b>",
        parse_mode="HTML",
    )
    await call.answer("✅ Подписка активирована!")

    try:
        await call.bot.send_message(
            target_id,
            "🎉 <b>Доступ активирован!</b>\n\n"
            f"Ваш <b>Paid</b>-план активен до <b>{paid_until[:10]}</b>.\n"
            "Теперь доступны все функции. Введите /menu",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Cannot notify user %s: %s", target_id, exc)
