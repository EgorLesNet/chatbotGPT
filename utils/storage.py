import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "db"
USERS_DIR = DB_DIR / "users"
MATERIALS_FILE = DB_DIR / "materials.json"


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


def suggest_materials(limit: int = 1) -> list[dict]:
    materials = _read_json(MATERIALS_FILE, [])
    return materials[:limit]


def list_rate_presets() -> list[dict]:
    return [
        {"name": "Штукатурка стен", "unit": "м²", "unit_price": 550, "note": "работа без материала"},
        {"name": "Стяжка пола", "unit": "м²", "unit_price": 750, "note": "базовый ориентир"},
        {"name": "Покраска потолка", "unit": "м²", "unit_price": 320, "note": "в 2 слоя"},
    ]
