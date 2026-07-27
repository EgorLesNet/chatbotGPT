"""Tribute — генерация ссылки на оплату."""
import os
from datetime import datetime, timedelta, timezone

TRIBUTE_DONATE_URL = os.getenv("TRIBUTE_DONATE_URL", "https://web.tribute.tg/d/NPF")


def get_tribute_pay_url(user_id: int) -> str:
    """Прямая ссылка на донат Tribute.
    user_id передаётся как comment чтобы админ видел кто заплатил.
    """
    return f"{TRIBUTE_DONATE_URL}?comment={user_id}"


def calc_paid_until(days: int = 30) -> str:
    """Дата окончания подписки (UTC ISO)."""
    until = datetime.now(timezone.utc) + timedelta(days=days)
    return until.isoformat()
