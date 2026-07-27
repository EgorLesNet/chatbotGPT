"""Tribute.fun — генерация ссылки на оплату."""
import os
from datetime import datetime, timedelta, timezone

TRIBUTE_BOT_USERNAME = os.getenv("TRIBUTE_BOT_USERNAME", "tribute")
TRIBUTE_PRODUCT_SLUG = os.getenv("TRIBUTE_PRODUCT_SLUG", "prorab-paid")


def get_tribute_pay_url(user_id: int) -> str:
    """Ссылка на оплату: https://t.me/tribute?start=prorab-paid_<user_id>"""
    return f"https://t.me/{TRIBUTE_BOT_USERNAME}?start={TRIBUTE_PRODUCT_SLUG}_{user_id}"


def calc_paid_until(days: int = 30) -> str:
    """Дата окончания подписки (UTC ISO)."""
    until = datetime.now(timezone.utc) + timedelta(days=days)
    return until.isoformat()
