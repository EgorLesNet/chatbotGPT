"""Логгирование каждого действия пользователя в db/logs/<user_id>.jsonl"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "db" / "logs"


def _ensure_logs_dir() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


_ensure_logs_dir()


def log_action(
    user_id: int,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Записывает одно событие в db/logs/<user_id>.jsonl (JSON Lines)."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details or {},
    }
    log_file = LOGS_DIR / f"{user_id}.jsonl"
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
