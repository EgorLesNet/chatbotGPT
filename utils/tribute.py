"""Tribute.fun — генерация ссылки на оплату и обработка уведомлений."""
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

TRIBUTE_SECRET = os.getenv("TRIBUTE_SECRET", "")
TRIBUTE_BOT_USERNAME = os.getenv("TRIBUTE_BOT_USERNAME", "tribute")
# Имя продукта в Tribute (slug), настраивается в кабинете
TRIBUTE_PRODUCT_SLUG = os.getenv("TRIBUTE_PRODUCT_SLUG", "prorab-paid")
PAID_PLAN_DAYS = int(os.getenv("PAID_PLAN_DAYS", "30"))


def get_tribute_pay_url(user_id: int) -> str:
    """
    Возвращает ссылку на оплату в Tribute.
    Payload: user_id передаётся через start-параметр deep link.
    Tribute поддерживает: https://t.me/<tribute_bot>?start=<product_slug>_<user_id>
    """
    return f"https://t.me/{TRIBUTE_BOT_USERNAME}?start={TRIBUTE_PRODUCT_SLUG}_{user_id}"


def verify_tribute_signature(data: dict, signature: str) -> bool:
    """
    Проверяет HMAC-SHA256 подпись вебхука от Tribute.
    Tribute отправляет: X-Tribute-Signature: sha256=<hex>
    """
    if not TRIBUTE_SECRET:
        return False
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    expected = hmac.new(
        TRIBUTE_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


def parse_tribute_webhook(payload: dict) -> dict | None:
    """
    Разбирает вебхук Tribute и возвращает dict с полями:
      user_id, amount, currency, product_slug, payment_id
    Возвращает None если payload не распознан.
    """
    try:
        # Tribute webhook structure (официальная дока)
        user_id_raw = (
            payload.get("user_id")
            or payload.get("metadata", {}).get("user_id")
            or payload.get("buyer", {}).get("telegram_id")
        )
        if not user_id_raw:
            return None
        return {
            "user_id": int(user_id_raw),
            "amount": payload.get("amount") or payload.get("price"),
            "currency": payload.get("currency", "RUB"),
            "product_slug": payload.get("product_slug") or payload.get("slug") or TRIBUTE_PRODUCT_SLUG,
            "payment_id": payload.get("payment_id") or payload.get("id"),
        }
    except (TypeError, ValueError):
        return None


def calc_paid_until() -> str:
    """Дата окончания подписки (UTC ISO)."""
    until = datetime.now(timezone.utc) + timedelta(days=PAID_PLAN_DAYS)
    return until.isoformat()
