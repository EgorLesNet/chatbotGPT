"""Обработчик вебхуков от Tribute.

Docs: https://wiki.tribute.tg/for-content-creators/api-documentation/webhooks

Поддерживаемые события:
  - newSubscription       — новая подписка
  - renewedSubscription   — продление подписки
  - cancelledSubscription — отмена подписки
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import date, timedelta

from aiogram import Bot

from storage import set_subscription

TRIBUTE_API_KEY = os.getenv("TRIBUTE_API_KEY", "")
SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))


def _verify_signature(body: bytes, signature: str) -> bool:
    """Проверка HMAC-SHA256 подписи от Tribute."""
    if not TRIBUTE_API_KEY:
        logging.warning("TRIBUTE_API_KEY не задан — подпись не проверяется!")
        return True
    expected = hmac.new(
        TRIBUTE_API_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_tribute_webhook(body: bytes, signature: str, bot: Bot):
    if not _verify_signature(body, signature):
        logging.warning("Tribute webhook: невалидная подпись, игнорируем")
        return

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logging.error("Tribute webhook: невалидный JSON")
        return

    event = data.get("event")
    payload = data.get("payload", {})

    # Telegram user_id приходит в поле subscriber.telegram_id
    subscriber = payload.get("subscriber", {})
    telegram_id = subscriber.get("telegram_id")

    if not telegram_id:
        logging.warning(f"Tribute webhook [{event}]: нет telegram_id в payload")
        return

    logging.info(f"Tribute webhook: event={event}, telegram_id={telegram_id}")

    if event in ("newSubscription", "renewedSubscription"):
        expires = str(date.today() + timedelta(days=SUBSCRIPTION_DAYS))
        set_subscription(int(telegram_id), subscribed=True, expires=expires)
        try:
            await bot.send_message(
                int(telegram_id),
                f"✅ Подписка активирована! Безлимитный доступ до <b>{expires}</b>."
                if event == "newSubscription" else
                f"🔄 Подписка продлена до <b>{expires}</b>. Спасибо!"
            )
        except Exception:
            logging.warning(f"Не удалось отправить сообщение пользователю {telegram_id}")

    elif event == "cancelledSubscription":
        set_subscription(int(telegram_id), subscribed=False, expires=None)
        try:
            await bot.send_message(
                int(telegram_id),
                "❌ Подписка отменена. Тебе доступно "
                f"{os.getenv('DAILY_FREE_LIMIT', '20')} бесплатных сообщений в день."
            )
        except Exception:
            logging.warning(f"Не удалось отправить сообщение пользователю {telegram_id}")

    else:
        logging.info(f"Tribute webhook: неизвестное событие {event}, пропускаем")
