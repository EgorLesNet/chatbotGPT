"""Простое JSON-хранилище пользователей с ежедневным сбросом счётчика."""
import json
import os
from datetime import date

DATA_FILE = os.getenv("DATA_FILE", "users.json")


def _load() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(user_id: int) -> dict:
    data = _load()
    uid = str(user_id)
    today = str(date.today())
    user = data.get(uid, {})

    # Сбрасываем счётчик, если новый день
    if user.get("date") != today:
        user["date"] = today
        user["daily_count"] = 0

    return user


def increment_messages(user_id: int, history: list):
    data = _load()
    uid = str(user_id)
    today = str(date.today())
    user = data.get(uid, {})

    if user.get("date") != today:
        user["date"] = today
        user["daily_count"] = 0

    user["daily_count"] = user.get("daily_count", 0) + 1
    user["history"] = history
    data[uid] = user
    _save(data)


def reset_history_for_user(user_id: int):
    data = _load()
    uid = str(user_id)
    if uid in data:
        data[uid]["history"] = []
    _save(data)
