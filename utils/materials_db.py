import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from utils.search import search_material_prices

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MATERIALS_FILE = BASE_DIR / "db" / "materials.json"


# ---------------------------------------------------------------------------
# Чтение / запись файла
# ---------------------------------------------------------------------------

def _load() -> dict:
    if not MATERIALS_FILE.exists():
        return {"meta": {}, "items": []}
    with MATERIALS_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(data: dict) -> None:
    with MATERIALS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}"


# ---------------------------------------------------------------------------
# Поиск по базе
# ---------------------------------------------------------------------------

def _score(item: dict, keywords: list[str]) -> int:
    """Count how many query keywords hit item keywords/name/category."""
    item_text = " ".join([
        item.get("name", ""),
        item.get("category", ""),
        " ".join(item.get("keywords", [])),
    ]).lower()
    return sum(1 for kw in keywords if kw.lower() in item_text)


def find_in_db(situation: str, limit: int = 3) -> list[dict]:
    """
    Ищет материалы в локальной базе по ключевым словам из описания ситуации.
    Возвращает материалы с наибольшим совпадением ключевых слов.
    """
    data = _load()
    words = situation.lower().split()
    scored = [(item, _score(item, words)) for item in data.get("items", [])]
    scored = [(item, sc) for item, sc in scored if sc > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in scored[:limit]]


def format_db_context(items: list[dict]) -> str:
    """Format found DB items as text block for LLM prompt."""
    if not items:
        return ""
    lines = ["Из локальной базы материалов:"]
    for item in items:
        lines.append(
            f"- {item['name']} ({item['category']}): "
            f"{item['price_range']}, ед. — {item['unit']}. "
            f"{item['use_case']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ежемесячная синхронизация цен
# ---------------------------------------------------------------------------

def needs_sync() -> bool:
    """True if the DB has not been synced this calendar month."""
    data = _load()
    return data.get("meta", {}).get("sync_month") != _current_month()


async def sync_prices_if_needed() -> bool:
    """
    Делает синхронизацию цен через интернет, если нужно.
    Возвращает True если синхронизация была выполнена.
    """
    if not needs_sync():
        return False

    logger.info("Starting monthly materials price sync...")
    data = _load()
    items = data.get("items", [])
    updated_count = 0

    for item in items:
        query = f"цена {item['name']} купить Россия 2026"
        web_result = await search_material_prices(query)
        if web_result:
            item["web_price_hint"] = web_result[:400]
            item["updated_at"] = _now_iso()
            updated_count += 1

    data["meta"]["sync_month"] = _current_month()
    data["meta"]["synced_at"] = _now_iso()
    _save(data)
    logger.info("Sync complete: %d items updated", updated_count)
    return True


# ---------------------------------------------------------------------------
# Основная функция: база → fallback в интернет
# ---------------------------------------------------------------------------

async def get_materials_context(situation: str, limit: int = 3) -> str:
    """
    1. Ищет материалы в локальной базе.
    2. Если ничего не нашлось — идёт в интернет.
    3. Возвращает текстовый блок для вставки в промпт LLM.
    """
    # Триггерим синхронизацию без ожидания (не блокируем ответ)
    import asyncio
    asyncio.ensure_future(sync_prices_if_needed())

    found = find_in_db(situation, limit=limit)

    if found:
        context = format_db_context(found)
        # Если у найденных позиций есть web_price_hint — добавляем
        hints = [
            f"- {i['name']}: {i['web_price_hint']}"
            for i in found if i.get("web_price_hint")
        ]
        if hints:
            context += "\nАктуальные цены из сети:\n" + "\n".join(hints)
        logger.debug("DB hit: %d items found for '%s'", len(found), situation[:50])
        return context

    # Fallback: ищем в интернете
    logger.info("DB miss for '%s', falling back to web search", situation[:50])
    web = await search_material_prices(situation)
    if web:
        return f"Актуальные данные из интернета (база не содержит подходящих материалов):\n{web}"
    return ""
