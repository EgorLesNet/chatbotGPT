import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "db"
USERS_DIR = DB_DIR / "users"
MATERIALS_FILE = DB_DIR / "materials.json"

DEFAULT_RATE_PRESETS = [
    {"name": "Демонтаж покрытия", "unit": "м²", "unit_price": 300, "note": "базовый ориентир"},
    {"name": "Стяжка пола", "unit": "м²", "unit_price": 750, "note": "работа без материала"},
    {"name": "Укладка кварцвинила", "unit": "м²", "unit_price": 650, "note": "на готовое основание"},
]


def ensure_dirs() -> None:
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)


ensure_dirs()


def _user_file(user_id: int) -> Path:
    return USERS_DIR / f"{user_id}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_month_key() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def ensure_user(telegram_user) -> dict:
    user_id = telegram_user.id
    existing = get_user(user_id)
    if existing:
        changed = False
        if "rate_presets" not in existing:
            existing["rate_presets"] = DEFAULT_RATE_PRESETS.copy()
            changed = True
        if changed:
            save_user(existing)
        return existing
    payload = {
        "id": user_id,
        "username": telegram_user.username,
        "full_name": telegram_user.full_name,
        "created_at": _now_iso(),
        "paid_until": None,
        "projects": [],
        "usage": {"month": _current_month_key(), "projects_created": 0},
        "preferences": {"voice_enabled": False, "pdf_enabled": False},
        "rate_presets": DEFAULT_RATE_PRESETS.copy(),
    }
    save_user(payload)
    return payload


def get_user(user_id: int) -> dict:
    return _read_json(_user_file(user_id), {})


def save_user(user: dict) -> None:
    _write_json(_user_file(user["id"]), user)


def reset_user_month(user_id: int) -> dict:
    user = get_user(user_id)
    if not user:
        return {}
    month = _current_month_key()
    if user.get("usage", {}).get("month") != month:
        user["usage"] = {"month": month, "projects_created": 0}
        save_user(user)
    return user


def create_project(user_id: int, title: str, project_type: str, area_m2: int, notes: str) -> dict:
    user = reset_user_month(user_id)
    project = {
        "id": f"prj-{user_id}-{len(user.get('projects', [])) + 1}",
        "title": title,
        "project_type": project_type,
        "area_m2": area_m2,
        "notes": notes,
        "created_at": _now_iso(),
    }
    user.setdefault("projects", []).append(project)
    user.setdefault("usage", {}).setdefault("projects_created", 0)
    user["usage"]["projects_created"] += 1
    save_user(user)
    return project


def get_user_projects(user_id: int) -> list[dict]:
    user = get_user(user_id)
    return user.get("projects", [])


def get_user_summary(user_id: int) -> dict:
    user = get_user(user_id)
    usage = user.get("usage", {})
    return {
        "projects_created_this_month": usage.get("projects_created", 0),
        "month": usage.get("month", _current_month_key()),
    }


def get_user_rates(user_id: int) -> list[dict]:
    user = get_user(user_id)
    rates = user.get("rate_presets") or DEFAULT_RATE_PRESETS.copy()
    return rates


def save_user_rates(user_id: int, rates: list[dict]) -> list[dict]:
    user = get_user(user_id)
    user["rate_presets"] = rates
    save_user(user)
    return rates


def _load_materials() -> list[dict]:
    raw = _read_json(MATERIALS_FILE, [])
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("items", [])
    return []


def suggest_materials(limit: int = 1) -> list[dict]:
    return _load_materials()[:limit]


def list_rate_presets() -> list[dict]:
    return DEFAULT_RATE_PRESETS.copy()
