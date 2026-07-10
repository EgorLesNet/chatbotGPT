import os
import json
import logging
import asyncio
import re
import math
import httpx
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, NotFoundError, RateLimitError, APIStatusError
from utils.materials_db import get_materials_context
from utils.storage import get_user_rates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Правила цен для импортных материалов по стране происхождения + категории
# (min_price, unit) — нижняя граница; если в смете ниже — поднимаем до min
# ---------------------------------------------------------------------------
_IMPORT_PRICE_RULES: list[dict] = [
    # Напольные покрытия
    {"countries": ["польш", "poland", "польск"], "keywords": ["кварцвинил", "vinyl", "lvt", "ламинат", "laminate"], "min_price": 3500, "unit": "м²"},
    {"countries": ["герман", "germany", "deutsch"], "keywords": ["кварцвинил", "vinyl", "lvt", "ламинат", "laminate", "паркет", "parquet"], "min_price": 4000, "unit": "м²"},
    {"countries": ["бельги", "belgium"], "keywords": ["ламинат", "laminate", "паркет"], "min_price": 3800, "unit": "м²"},
    # Плитка
    {"countries": ["итали", "italy", "italian"], "keywords": ["плитк", "tile", "керам", "porcel"], "min_price": 2500, "unit": "м²"},
    {"countries": ["испани", "spain", "spanish"], "keywords": ["плитк", "tile", "керам"], "min_price": 2000, "unit": "м²"},
    # Краски
    {"countries": ["финлянд", "finland", "финск"], "keywords": ["краск", "paint", "эмаль"], "min_price": 800, "unit": "л"},
    {"countries": ["герман", "germany", "deutsch"], "keywords": ["краск", "paint", "эмаль"], "min_price": 900, "unit": "л"},
]

# Нормальная пропорция работы/материалы для ремонта: работы не менее 25% от общей суммы
_MIN_WORKS_RATIO = 0.25
# Минимальный процентный разрыв между вариантами (25% от предыдущего)
_MIN_TIER_GAP_PCT = 0.25
# Потолок цены напольного покрытия для Эконома (₽/м²)
_ECONOM_FLOOR_MAX_PRICE = 1900
# Ключевые слова напольных покрытий
_FLOOR_COVERING_KEYWORDS = ["кварцвинил", "ламинат", "линолеум", "vinyl", "laminate", "lvt", "покрытие пол", "напольн"]
# Фразы самокритики, которые нельзя оставлять в выводе
_SELF_DOUBT_PHRASES = [
    "требует уточнения", "неуверен в цифрах", "приблизительно", "возможно неточно",
    "данные могут отличаться", "рекомендуется уточнить", "уточните у специалиста",
    "не могу гарантировать точность", "ориентировочные данные",
]


SYSTEM_PROMPT = """
Ты — опытный прораб-сметчик в России.

Твоя задача — оценить ПРИМЕРНУЮ СТОИМОСТЬ ремонта по смыслу задачи.
Сначала определи масштаб задачи, потом считай смету.

КРИТИЧЕСКИ ВАЖНО:
- Если пользователь описывает полный ремонт квартиры / ремонт под ключ / капитальный ремонт — включай ВСЕ разделы: демонтаж, стены, полы, потолки, электрика, сантехника, чистовая отделка, монтаж.
- Для локальных задач считай только относящиеся к ним этапы.
- Стоимость работ считай по расценкам мастера, если переданы; иначе — рыночная оценка.
- Материалы подбирай адекватно задаче, не ограничивайся 1–2 позициями.
- Эконом, Оптимальный и Премиум различаются качеством, брендами и объёмом решений.

ПРАВИЛА АРИФМЕТИКИ (КРИТИЧНО):
- Каждая строка: qty × unit_price = total. После расчёта проверь умножением ещё раз. Если total ≠ qty × unit_price — пересчитай и исправь перед выводом.
- После формирования сметы пересчитай total_works = сумма всех works[].total, total_materials = сумма всех materials[].total, total = total_works + total_materials. Если не совпадает с указанным Итого — найди и исправь ошибочную строку.
- Никогда не выводи строку с заведомо неверным итогом.

ПРАВИЛА РАСЧЁТА МАТЕРИАЛОВ:
- quantity = ceiling((площадь × норма расхода) / вес_или_объём_упаковки). Никогда не ставь произвольно.
- Для каждого сыпучего/жидкого материала указывай норму расхода в названии или бренде: "Расход 8.5 кг/м²".
- Если материал — импортный (Польша, Германия, Италия, Бельгия, Финляндия и т.д.), цена не может быть ниже среднерыночной для этой категории. Польский/немецкий кварцвинил и ламинат — от 3 500 ₽/м². Итальянская плитка — от 2 500 ₽/м². Если цена не соответствует стране — используй отечественный аналог или скорректируй цену.
- Для варианта «Эконом»: цена напольного покрытия (кварцвинил, ламинат, линолеум) не должна превышать 1 900 ₽/м². Если выбранный материал дороже — используй более бюджетный аналог или перемести его в «Оптимальный».

ПРАВИЛА СИНХРОНИЗАЦИИ ПЛОЩАДЕЙ:
- Если в смете несколько типов напольного покрытия (кварцвинил, плитка, ламинат), сумма их площадей (qty) должна точно равняться общей площади пола в проекте.
- Для каждого типа напольного покрытия должна быть отдельная строка работы по укладке с той же площадью.

ПРАВИЛА РАБОТ И СООТНОШЕНИЙ:
- Штукатурка потолков — на 20–40% дороже штукатурки стен.
- Перед штукатуркой обязательно добавляй грунтовку основания отдельной строкой работ и материалов.
- Работы должны составлять не менее 30–40% от итоговой суммы варианта. Если материалы в 10+ раз превышают работы — это ошибка, пересчитай пропорцию.
- Каждый вариант (Эконом / Оптимальный / Премиум) должен содержать полный набор этапов работ и материалов. Премиум не может иметь меньше этапов работ, чем Эконом.

ПРАВИЛА ГРАДАЦИИ ЦЕН:
- Итог Премиум должен быть на 25–50% больше Оптимального, Оптимальный — на 20–30% больше Эконома.
- Если расчёт не выдаёт этот разрыв — увеличивай стоимость материалов/работ следующего уровня.
- cost_min = минимальный total среди трёх вариантов; cost_max = максимальный. Никогда не ставь в 0.

ПРАВИЛА ОФОРМЛЕНИЯ ВЫВОДА:
- Никогда не включай в финальный JSON фразы вида «требует уточнения», «неуверен в цифрах», «рекомендуется уточнить» и подобные. Если данных недостаточно — либо дополни расчёт разумными допущениями, либо полностью убери соответствующую секцию.

ОСТАЛЬНЫЕ ПРАВИЛА:
- total_works = сумма works.total; total_materials = сумма materials.total; total = total_works + total_materials.
- Никогда не оставляй пустые pros/cons и не отдавай вариант с 0 материалов.
- Диапазон cost_min/cost_max строго совпадает с min/max total среди вариантов.

Верни ONLY raw JSON:
{
  "summary": "",
  "cost_min": 0,
  "cost_max": 0,
  "currency": "₽",
  "variants": [
    {
      "name": "Эконом",
      "style": "Бюджетный",
      "total_works": 0,
      "total_materials": 0,
      "total": 0,
      "budget": "",
      "works": [{"name": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}],
      "materials": [{"name": "", "brand": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}],
      "pros": "",
      "cons": ""
    },
    {
      "name": "Оптимальный",
      "style": "Средний",
      "total_works": 0,
      "total_materials": 0,
      "total": 0,
      "budget": "",
      "works": [{"name": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}],
      "materials": [{"name": "", "brand": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}],
      "pros": "",
      "cons": ""
    },
    {
      "name": "Премиум",
      "style": "Дизайнерский",
      "total_works": 0,
      "total_materials": 0,
      "total": 0,
      "budget": "",
      "works": [{"name": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}],
      "materials": [{"name": "", "brand": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}],
      "pros": "",
      "cons": ""
    }
  ],
  "risks": ""
}
""".strip()

SYSTEM_PROMPT_GROQ = (
    "Ты — прораб-сметчик в России. Смета ремонта в 3 вариантах (Эконом/Оптимальный/Премиум). "
    "Полный ремонт: включай демонтаж, стены, полы, потолки, электрику, сантехнику, чистовую отделку. "
    "Используй расценки мастера, если переданы. "
    "АРИФМЕТИКА: каждая строка qty×unit_price=total — проверь умножением. После смет пересчитай total_works и total как суммы строк. Если не совпадает — исправь. "
    "Материалы считай только математически по норме расхода, округляй вверх. "
    "Для сыпучих/жидких — указывай норму расхода в названии/бренде. "
    "Импортный материал (Польша, Германия и т.д.): цена не ниже рынка — польский/немецкий кварцвинил от 3500₽/м², итальянская плитка от 2500₽/м²; иначе замени на отечественный аналог. "
    "Эконом: напольное покрытие не дороже 1900₽/м²; если дороже — замени на бюджетный аналог или перемести в Оптимальный. "
    "Несколько типов напольного покрытия: сумма их площадей = общая площадь пола; для каждого — отдельная строка укладки. "
    "Штукатурка потолков — на 20-40% дороже стен. Грунтовка перед штукатуркой — обязательно. "
    "Работы >= 30% от итога варианта. Каждый вариант — полный набор этапов, Премиум не менее этапов, чем Эконом. "
    "Разрыв цен: Оптимальный на 20-30% больше Эконома, Премиум на 25-50% больше Оптимального. "
    "Не включай фразы 'требует уточнения', 'неуверен в цифрах' и подобные — замени допущениями или убери секцию. "
    "Никогда не ставь cost_min/cost_max в 0; диапазон = min/max total; не отдавай пустые варианты. "
    "Отвечай ONLY чистым JSON:"
    '{"summary":"","cost_min":0,"cost_max":0,"currency":"₽","variants":['
    '{"name":"Эконом","style":"Бюджетный","total_works":0,"total_materials":0,"total":0,"budget":"","works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],"pros":"","cons":""},'
    '{"name":"Оптимальный","style":"Средний","total_works":0,"total_materials":0,"total":0,"budget":"","works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],"pros":"","cons":""},'
    '{"name":"Премиум","style":"Дизайнерский","total_works":0,"total_materials":0,"total":0,"budget":"","works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],"pros":"","cons":""}'
    '],"risks":""}'
)

SYSTEM_PROMPT_LOCAL = (
    "Отвечай ONLY чистым JSON. Смета ремонта в РФ в 3 вариантах. "
    "АРИФМЕТИКА: qty×unit_price=total в каждой строке; total_works и total = суммы строк. Проверь перед выводом. "
    "Используй расценки мастера, если переданы. "
    "Материалы — только по норме расхода через арифметику. "
    "Импортный материал: цена не ниже рынка. Эконом: напольное покрытие <= 1900₽/м². "
    "Несколько типов пола: сумма площадей = площадь пола; для каждого — строка укладки. "
    "Работы >= 30% итога. Полный набор этапов в каждом варианте. "
    "Разрыв: Оптимальный > Эконом на 20%+, Премиум > Оптимальный на 25%+. "
    "Без фраз 'требует уточнения' и подобных. "
    "cost_min/cost_max = min/max total. Не оставляй пустые варианты. "
    '{"summary":"","cost_min":0,"cost_max":0,"currency":"₽","variants":['
    '{"name":"Эконом","style":"","total_works":0,"total_materials":0,"total":0,"budget":"","works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],"pros":"","cons":""},'
    '{"name":"Оптимальный","style":"","total_works":0,"total_materials":0,"total":0,"budget":"","works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],"pros":"","cons":""},'
    '{"name":"Премиум","style":"","total_works":0,"total_materials":0,"total":0,"budget":"","works":[{"name":"","unit":"","qty":0,"unit_price":0,"total":0}],"materials":[{"name":"","brand":"","unit":"","qty":0,"unit_price":0,"total":0}],"pros":"","cons":""}'
    '],"risks":""}'
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
LLAMACPP_DEFAULT_URL = "http://localhost:11434"

GROQ_DEFAULT_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

HTTPX_TIMEOUT_LOCAL = httpx.Timeout(connect=5.0, read=600.0, write=15.0, pool=5.0)
HTTPX_TIMEOUT_CLOUD = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=5.0)

RETRY_DELAYS = [3, 10]
MAX_RATE_LIMIT_WAIT = 30
JSON_MAX_RETRIES = 2

_BLOCKLIST_KEYWORDS = ["content-safety", "moderation", "guard", "embedding", "rerank", "classify", "whisper", "tts"]
_free_models_cache: list[str] = []


def _is_chat_model(model_id: str) -> bool:
    return not any(kw in model_id.lower() for kw in _BLOCKLIST_KEYWORDS)


def _is_local(base_url: str) -> bool:
    return "localhost" in base_url or "127.0.0.1" in base_url


def _is_groq(base_url: str) -> bool:
    return "groq.com" in base_url


async def _check_llamacpp() -> tuple[str, str] | None:
    base_url = os.getenv("LLAMACPP_URL", LLAMACPP_DEFAULT_URL).rstrip("/")
    model_name = os.getenv("LLAMACPP_MODEL", "local-model")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/health")
            if resp.status_code == 200:
                logger.info("llama.cpp server is up: %s", model_name)
                return model_name, f"{base_url}/v1"
    except Exception:
        pass
    logger.info("llama.cpp not available at %s", base_url)
    return None


def _get_groq_models() -> list[tuple[str, str]]:
    if not os.getenv("GROQ_API_KEY", "").strip():
        return []
    custom = os.getenv("GROQ_MODEL", "").strip()
    models = [custom] if custom else GROQ_DEFAULT_MODELS
    return [(m, GROQ_BASE_URL) for m in models]


async def fetch_free_models(api_key: str) -> list[str]:
    global _free_models_cache
    if _free_models_cache:
        return _free_models_cache
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{OPENROUTER_BASE_URL}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        free = [
            m["id"] for m in data.get("data", [])
            if (m["id"].endswith(":free") or str(m.get("pricing", {}).get("prompt", "1")) == "0")
            and _is_chat_model(m["id"])
        ]
        priority = ["llama", "gemma", "qwen", "nemotron", "hermes", "mistral"]
        free.sort(key=lambda mid: next((i for i, kw in enumerate(priority) if kw in mid), len(priority)))
        _free_models_cache = free[:10]
        logger.info("Loaded %d free chat models from OpenRouter", len(_free_models_cache))
        return _free_models_cache
    except Exception:
        logger.warning("OpenRouter unavailable, skipping cloud models")
        return []


def _make_client(base_url: str, api_key: str) -> AsyncOpenAI:
    local = _is_local(base_url)
    groq = _is_groq(base_url)
    if local:
        effective_key = "local"
    elif groq:
        effective_key = os.getenv("GROQ_API_KEY", "")
    else:
        effective_key = api_key
    return AsyncOpenAI(
        api_key=effective_key,
        base_url=base_url,
        timeout=HTTPX_TIMEOUT_LOCAL if local else HTTPX_TIMEOUT_CLOUD,
        max_retries=0,
        default_headers={} if (local or groq) else {
            "HTTP-Referer": os.getenv("APP_URL", "https://github.com/EgorLesNet/chatbotGPT"),
            "X-Title": "ProrabBot",
        },
    )


async def _get_model_chain(api_key: str) -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = []
    for groq_entry in _get_groq_models():
        chain.append(groq_entry)
    local = await _check_llamacpp()
    if local:
        chain.append(local)
    primary = os.getenv("OPENROUTER_MODEL", "").strip()
    if primary:
        chain.append((primary, OPENROUTER_BASE_URL))
    for m in await fetch_free_models(api_key):
        if not any(m == c[0] for c in chain):
            chain.append((m, OPENROUTER_BASE_URL))
    if not chain:
        logger.error("No models available")
    return chain


def _detect_scope(situation: str) -> dict:
    s = (situation or "").lower()
    full_markers = [
        "полный ремонт", "ремонт под ключ", "капитальный ремонт",
        "современный ремонт", "квартира целиком", "всей квартиры",
        "с инженер", "с сантехник", "электрик", "чернов", "чистов",
    ]
    floor_markers = ["пол", "стяжк", "кварцвинил", "ламинат", "плитк", "линолеум"]
    bath_markers = ["ванн", "сануз", "туалет", "душ"]
    paint_markers = ["покраск", "обои", "шпаклев", "штукатур"]

    if any(x in s for x in full_markers):
        return {
            "scope": "full_apartment",
            "required_sections": [
                "демонтаж", "черновые стены", "черновые полы",
                "электрика", "сантехника", "чистовая отделка стен",
                "чистовые полы", "потолки", "двери/плинтусы/фурнитура",
            ],
        }
    if any(x in s for x in bath_markers):
        return {
            "scope": "bathroom",
            "required_sections": ["демонтаж", "сантехника", "гидроизоляция", "плиточные работы", "чистовой монтаж"],
        }
    if any(x in s for x in floor_markers):
        return {
            "scope": "floor_only",
            "required_sections": ["демонтаж", "подготовка основания", "стяжка/выравнивание", "финишное покрытие"],
        }
    if any(x in s for x in paint_markers):
        return {
            "scope": "walls_finish",
            "required_sections": ["подготовка", "выравнивание", "финишная отделка"],
        }
    return {"scope": "generic", "required_sections": []}


def _build_rates_context(user_rates: list[dict]) -> str:
    if not user_rates:
        return ""
    lines = ["Расценки мастера по работам (используй их в первую очередь):"]
    for item in user_rates:
        lines.append(f"- {item.get('name','')}: {item.get('unit_price',0)} ₽/{item.get('unit','')} ({item.get('note','')})")
    return "\n".join(lines)


def _build_user_message(situation: str, project: dict | None, materials_context: str, rates_context: str, scope_info: dict) -> str:
    parts = [f"Ситуация: {situation}"]
    if project:
        parts.append(f"Объект: {project.get('title', '')}, тип: {project.get('project_type', '')}, {project.get('area_m2', '')} м²")
        if project.get("notes"):
            parts.append(f"Заметки: {project['notes']}")
    parts.append(f"Определённый тип задачи: {scope_info.get('scope', 'generic')}")
    required_sections = scope_info.get("required_sections") or []
    if required_sections:
        parts.append("Обязательные разделы сметы:")
        for item in required_sections:
            parts.append(f"- {item}")
    if rates_context:
        parts.append(rates_context)
    if materials_context:
        parts.append(materials_context)
    return "\n".join(parts)


def _clean_json(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = raw.replace("```", "").strip()
    start = raw.find("{")
    if start == -1:
        return raw
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(raw[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return raw[start:]


def _norm_int(val) -> int:
    try:
        return int(float(str(val).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _ceil_int(val: float) -> int:
    try:
        return int(math.ceil(float(val)))
    except (TypeError, ValueError):
        return 0


def _extract_consumption(text: str) -> float | None:
    if not text:
        return None
    s = str(text).lower().replace(",", ".")
    patterns = [
        r"расход\s*(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*кг/м[2²]",
        r"(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*кг/м[2²]",
        r"расход\s*(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*л/м[2²]",
        r"(\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(\d+(?:\.\d+)?)?\s*л/м[2²]",
    ]
    for pattern in patterns:
        m = re.search(pattern, s)
        if m:
            a = float(m.group(1))
            b = float(m.group(2)) if m.group(2) else None
            return (a + b) / 2 if b else a
    return None


def _extract_pack_weight_kg(text: str) -> float | None:
    if not text:
        return None
    s = str(text).lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*кг", s)
    return float(m.group(1)) if m else None


def _find_related_work_qty(works: list[dict], keywords: list[str]) -> int:
    max_qty = 0
    for w in works:
        name = (w.get("name") or "").lower()
        if any(k in name for k in keywords):
            max_qty = max(max_qty, _norm_int(w.get("qty") or 0))
    return max_qty


# ---------------------------------------------------------------------------
# ПРАВКА 1 + 5: Пост-валидация арифметики строк и итоговой суммы
# ---------------------------------------------------------------------------
def _fix_line_arithmetic(rows: list[dict]) -> list[dict]:
    """Для каждой строки: если total != qty*unit_price — пересчитываем total."""
    for row in rows:
        qty = _norm_int(row.get("qty") or 0)
        unit_price = _norm_int(row.get("unit_price") or 0)
        expected = qty * unit_price
        actual = _norm_int(row.get("total") or 0)
        if expected > 0 and actual != expected:
            logger.info(
                "Arithmetic fix '%s': total %d -> %d (qty=%d × price=%d)",
                row.get("name"), actual, expected, qty, unit_price
            )
            row["total"] = expected
    return rows


# ---------------------------------------------------------------------------
# ПРАВКА 2: Синхронизация площади напольных покрытий
# ---------------------------------------------------------------------------
def _fix_floor_area_sync(
    works: list[dict],
    materials: list[dict],
    project_area: float | None,
) -> tuple[list[dict], list[dict]]:
    """Проверяет, что сумма площадей напольных покрытий = площади пола.
    Для каждого покрытия добавляет строку укладки, если её нет.
    Если площадь проекта неизвестна — только добавляем укладку."""
    floor_mats = [
        m for m in materials
        if any(kw in (m.get("name") or "").lower() for kw in _FLOOR_COVERING_KEYWORDS)
        and ("м²" in (m.get("unit") or "") or "м2" in (m.get("unit") or "") or (m.get("unit") or "") in ("", "м"))
    ]
    if not floor_mats:
        return works, materials

    # Если площадь проекта известна и покрытий несколько — проверяем сумму
    if project_area and len(floor_mats) > 1:
        total_floor_qty = sum(_norm_int(m.get("qty")) for m in floor_mats)
        if total_floor_qty != _ceil_int(project_area):
            # Масштабируем пропорционально до нужной суммы
            scale = project_area / max(total_floor_qty, 1)
            logger.info(
                "Floor area sync: total_qty=%d -> project_area=%.1f, scale=%.3f",
                total_floor_qty, project_area, scale
            )
            remaining = _ceil_int(project_area)
            for i, m in enumerate(floor_mats):
                if i < len(floor_mats) - 1:
                    new_qty = max(1, round(_norm_int(m.get("qty")) * scale))
                    m["qty"] = new_qty
                    remaining -= new_qty
                else:
                    m["qty"] = max(1, remaining)
                m["total"] = m["qty"] * _norm_int(m.get("unit_price") or 0)

    # Для каждого напольного материала убеждаемся, что есть строка укладки
    for m in floor_mats:
        mat_name = (m.get("name") or "").lower()
        mat_qty = _norm_int(m.get("qty"))
        # Ищем соответствующую строку укладки
        has_install_work = any(
            ("укладк" in (w.get("name") or "").lower() or "монтаж" in (w.get("name") or "").lower())
            and any(kw in (w.get("name") or "").lower() for kw in _FLOOR_COVERING_KEYWORDS)
            and _norm_int(w.get("qty")) == mat_qty
            for w in works
        )
        if not has_install_work and mat_qty > 0:
            # Определяем тип покрытия для названия работы
            if "плитк" in mat_name or "tile" in mat_name or "керам" in mat_name:
                work_name = "Укладка плитки"
                unit_price = 900
            elif "кварцвинил" in mat_name or "vinyl" in mat_name or "lvt" in mat_name:
                work_name = "Укладка кварцвинила"
                unit_price = 400
            elif "паркет" in mat_name or "parquet" in mat_name:
                work_name = "Укладка паркетной доски"
                unit_price = 600
            else:
                work_name = "Укладка напольного покрытия"
                unit_price = 350
            works.append({
                "name": work_name,
                "unit": "м²",
                "qty": mat_qty,
                "unit_price": unit_price,
                "total": mat_qty * unit_price,
            })
            logger.info("Floor install work added: '%s' %d м²", work_name, mat_qty)
    return works, materials


# ---------------------------------------------------------------------------
# ПРАВКА 3: Удаление фраз самокритики из строковых полей
# ---------------------------------------------------------------------------
def _fix_self_doubt_phrases(variant: dict) -> dict:
    """Удаляет/заменяет самокритичные фразы из pros, cons, summary, budget."""
    fields_to_clean = ["pros", "cons", "budget", "summary"]
    for field in fields_to_clean:
        val = variant.get(field) or ""
        if not val:
            continue
        val_lower = val.lower()
        if any(phrase in val_lower for phrase in _SELF_DOUBT_PHRASES):
            # Убираем только проблемную фразу, оставляем остальное
            cleaned = val
            for phrase in _SELF_DOUBT_PHRASES:
                # Удаляем предложение целиком, если оно содержит фразу
                sentences = re.split(r'(?<=[.!?])\s+', cleaned)
                sentences = [
                    s for s in sentences
                    if phrase not in s.lower()
                ]
                cleaned = " ".join(sentences).strip()
            variant[field] = cleaned if cleaned else variant.get(field, "")
    # Очищаем названия строк работ и материалов
    for row in (variant.get("works") or []) + (variant.get("materials") or []):
        name = row.get("name") or ""
        if any(phrase in name.lower() for phrase in _SELF_DOUBT_PHRASES):
            row["name"] = re.sub(
                r"\s*[\(\[]?(?:" + "|".join(re.escape(p) for p in _SELF_DOUBT_PHRASES) + r")[^\)\]]*[\)\]]?\s*",
                "", name, flags=re.IGNORECASE
            ).strip()
    return variant


# ---------------------------------------------------------------------------
# ПРАВКА 4: Потолок цены напольного покрытия для Эконома
# ---------------------------------------------------------------------------
def _fix_econom_floor_cap(variant: dict) -> dict:
    """Для Эконом-варианта: напольное покрытие не дороже _ECONOM_FLOOR_MAX_PRICE ₽/м².
    Если дороже — снижаем до потолка и пересчитываем total."""
    if (variant.get("name") or "").lower() not in ("эконом", "econom", "economy", "бюджетный"):
        return variant
    for m in (variant.get("materials") or []):
        name = (m.get("name") or "").lower()
        unit = (m.get("unit") or "").lower()
        is_floor = any(kw in name for kw in _FLOOR_COVERING_KEYWORDS)
        is_per_sqm = "м²" in unit or "м2" in unit or unit in ("", "м")
        if not (is_floor and is_per_sqm):
            continue
        unit_price = _norm_int(m.get("unit_price") or 0)
        if unit_price > _ECONOM_FLOOR_MAX_PRICE:
            logger.info(
                "Econom floor cap: '%s' %d -> %d ₽/м²",
                m.get("name"), unit_price, _ECONOM_FLOOR_MAX_PRICE
            )
            m["unit_price"] = _ECONOM_FLOOR_MAX_PRICE
            qty = max(_norm_int(m.get("qty")), 1)
            m["total"] = qty * _ECONOM_FLOOR_MAX_PRICE
    return variant


# ---------------------------------------------------------------------------
# Проверка цен импортных материалов
# ---------------------------------------------------------------------------
def _fix_import_prices(materials: list[dict]) -> list[dict]:
    for m in materials:
        name = (m.get("name") or "").lower()
        brand = (m.get("brand") or "").lower()
        text = f"{name} {brand}"
        unit = (m.get("unit") or "").lower()
        unit_price = _norm_int(m.get("unit_price") or 0)
        if unit_price <= 0:
            continue
        for rule in _IMPORT_PRICE_RULES:
            country_match = any(c in text for c in rule["countries"])
            keyword_match = any(k in text for k in rule["keywords"])
            if not (country_match and keyword_match):
                continue
            rule_unit = rule["unit"]
            unit_ok = (rule_unit == "м²" and ("м²" in unit or "м2" in unit or unit in ("", "м")))
            unit_ok = unit_ok or (rule_unit == "л" and "л" in unit)
            unit_ok = unit_ok or (rule_unit not in ("м²", "л"))
            if not unit_ok:
                continue
            if unit_price < rule["min_price"]:
                logger.info(
                    "Import price guard: '%s' raised from %d to %d ₽/%s",
                    m.get("name"), unit_price, rule["min_price"], rule_unit
                )
                m["unit_price"] = rule["min_price"]
                qty = max(_norm_int(m.get("qty")), 1)
                m["total"] = qty * rule["min_price"]
                if m.get("brand") and "польш" not in (m.get("brand") or "").lower() and "germa" not in (m.get("brand") or "").lower():
                    m["brand"] = m["brand"] + f" (скорр. цена: от {rule['min_price']} ₽/{rule_unit})"
            break
    return materials


# ---------------------------------------------------------------------------
# Добавить грунтовку перед штукатуркой, если её нет
# ---------------------------------------------------------------------------
def _ensure_primer_before_plaster(works: list[dict], materials: list[dict], currency: str) -> tuple[list[dict], list[dict]]:
    has_plaster_work = any("штукатур" in (w.get("name") or "").lower() for w in works)
    has_plaster_mat = any("штукатур" in (m.get("name") or "").lower() for m in materials)
    if not (has_plaster_work or has_plaster_mat):
        return works, materials

    plaster_area = _find_related_work_qty(works, ["штукатур"])
    if plaster_area <= 0:
        return works, materials

    has_primer_work = any("грунт" in (w.get("name") or "").lower() for w in works)
    has_primer_mat = any("грунт" in (m.get("name") or "").lower() for m in materials)

    if not has_primer_work:
        unit_price = 80
        works.append({
            "name": "Грунтовка основания перед штукатуркой",
            "unit": "м²", "qty": plaster_area,
            "unit_price": unit_price, "total": plaster_area * unit_price,
        })
    if not has_primer_mat:
        consumption, pack_l, unit_price = 0.15, 10.0, 900
        qty = _ceil_int((plaster_area * consumption) / pack_l)
        materials.append({
            "name": f"Грунтовка глубокого проникновения, расход {consumption} л/м²",
            "brand": "Канистра 10 л", "unit": "шт",
            "qty": qty, "unit_price": unit_price, "total": qty * unit_price,
        })
    return works, materials


# ---------------------------------------------------------------------------
# Потолочная штукатурка >= 120% цены стеновой
# ---------------------------------------------------------------------------
def _fix_ceiling_plaster_prices(works: list[dict]) -> list[dict]:
    wall_prices = []
    for w in works:
        name = (w.get("name") or "").lower()
        if "штукатур" in name and "стен" in name and _norm_int(w.get("unit_price")) > 0:
            wall_prices.append(_norm_int(w.get("unit_price")))
    if not wall_prices:
        return works
    ceiling_min = _ceil_int(max(wall_prices) * 1.2)
    for w in works:
        name = (w.get("name") or "").lower()
        if "штукатур" in name and "потол" in name:
            qty = _norm_int(w.get("qty"))
            if _norm_int(w.get("unit_price")) < ceiling_min:
                w["unit_price"] = ceiling_min
                w["total"] = qty * ceiling_min
    return works


# ---------------------------------------------------------------------------
# Пересчёт количества штукатурки по норме расхода
# ---------------------------------------------------------------------------
def _fix_consumable_materials(works: list[dict], materials: list[dict]) -> list[dict]:
    plaster_area = _find_related_work_qty(works, ["штукатур"])
    if plaster_area <= 0:
        return materials
    for m in materials:
        name = (m.get("name") or "").lower()
        brand = (m.get("brand") or "").lower()
        text = f"{name} {brand}"
        if "штукатур" not in text:
            continue
        consumption = _extract_consumption(text)
        if consumption is None:
            consumption = 8.5
            m["brand"] = (m.get("brand") or "") + f" · Расход {consumption} кг/м²"
        pack_weight = _extract_pack_weight_kg(text)
        if pack_weight is None:
            pack_weight = 30.0
            m["brand"] = (m.get("brand") or "") + f" · Мешок {int(pack_weight)} кг"
        needed_qty = _ceil_int((plaster_area * consumption) / pack_weight)
        if needed_qty > _norm_int(m.get("qty")):
            m["qty"] = needed_qty
        m["total"] = m["qty"] * _norm_int(m.get("unit_price"))
    return materials


# ---------------------------------------------------------------------------
# Гарантия непустых pros/cons и materials
# ---------------------------------------------------------------------------
def _ensure_nonempty_variant_fields(variant: dict) -> dict:
    if not variant.get("pros"):
        variant["pros"] = "Сбалансирован по задачам и бюджету."
    if not variant.get("cons"):
        variant["cons"] = "Стоимость уточняется по финальному проекту."
    if not (variant.get("materials") or []):
        variant["materials"] = [{
            "name": "Материалы уточняются по проекту", "brand": "Предварительный расчёт",
            "unit": "компл", "qty": 1, "unit_price": 1, "total": 1,
        }]
    return variant


# ---------------------------------------------------------------------------
# Проверка пропорции работы/материалы: работы >= 25% от total
# ---------------------------------------------------------------------------
def _fix_works_ratio(works: list[dict], materials: list[dict]) -> list[dict]:
    total_works = sum(_norm_int(w.get("total")) for w in works)
    total_materials = sum(_norm_int(m.get("total")) for m in materials)
    total = total_works + total_materials
    if total <= 0 or total_works <= 0:
        return works
    ratio = total_works / total
    if ratio >= _MIN_WORKS_RATIO:
        return works
    target_works = _ceil_int(_MIN_WORKS_RATIO * total_materials / (1 - _MIN_WORKS_RATIO))
    scale = target_works / total_works
    logger.info("Works ratio fix: %.2f -> %.2f, scale=%.2f", ratio, _MIN_WORKS_RATIO, scale)
    for w in works:
        old = _norm_int(w.get("total"))
        if old <= 0:
            continue
        new_total = _ceil_int(old * scale)
        w["total"] = new_total
        qty = max(_norm_int(w.get("qty")), 1)
        w["unit_price"] = _ceil_int(new_total / qty)
    return works


# ---------------------------------------------------------------------------
# Гарантия минимального числа позиций в Премиум/Оптимальный
# ---------------------------------------------------------------------------
def _fix_variant_completeness(variants: list[dict]) -> list[dict]:
    if len(variants) < 2:
        return variants
    ref_works_count = max(len(v.get("works") or []) for v in variants[:2])
    ref_mats_count = max(len(v.get("materials") or []) for v in variants[:2])
    min_works_required = ref_works_count
    min_mats_required = _ceil_int(ref_mats_count * 0.8)

    for i, v in enumerate(variants):
        if i < 2:
            continue
        works_count = len(v.get("works") or [])
        mats_count = len(v.get("materials") or [])
        if works_count < min_works_required or mats_count < min_mats_required:
            logger.warning(
                "Variant '%s' incomplete: %d works (need %d), %d mats (need %d)",
                v.get("name"), works_count, min_works_required, mats_count, min_mats_required
            )
            v["_incomplete"] = True
    return variants


# ---------------------------------------------------------------------------
# Enforce 25% min gap между вариантами
# ---------------------------------------------------------------------------
def _enforce_variant_order(variants: list[dict]) -> list[dict]:
    prev_total = 0
    for i, v in enumerate(variants):
        total_works = sum(_norm_int(w.get("total")) for w in (v.get("works") or []))
        total_materials = sum(_norm_int(m.get("total")) for m in (v.get("materials") or []))
        total = total_works + total_materials

        if i > 0 and prev_total > 0:
            min_required = _ceil_int(prev_total * (1 + _MIN_TIER_GAP_PCT))
            if total < min_required:
                diff = min_required - total
                logger.info(
                    "Tier gap fix for '%s': total %d -> %d (+%d)",
                    v.get("name"), total, min_required, diff
                )
                if v.get("works"):
                    works_total = sum(_norm_int(w.get("total")) for w in v["works"])
                    if works_total > 0:
                        for w in v["works"]:
                            share = _norm_int(w.get("total")) / works_total
                            addition = _ceil_int(diff * share)
                            w["total"] = _norm_int(w.get("total")) + addition
                            qty = max(_norm_int(w.get("qty")), 1)
                            w["unit_price"] = _ceil_int(w["total"] / qty)
                        new_works_total = sum(_norm_int(w.get("total")) for w in v["works"])
                        remainder = min_required - (new_works_total + total_materials)
                        if remainder > 0:
                            last_w = v["works"][-1]
                            last_w["total"] = _norm_int(last_w.get("total")) + remainder
                            qty = max(_norm_int(last_w.get("qty")), 1)
                            last_w["unit_price"] = _ceil_int(last_w["total"] / qty)
                    else:
                        v["works"].append({
                            "name": "Дополнительные работы сегмента",
                            "unit": "компл", "qty": 1,
                            "unit_price": diff, "total": diff,
                        })
                elif v.get("materials"):
                    last_m = v["materials"][-1]
                    last_m["total"] = _norm_int(last_m.get("total")) + diff
                    qty = max(_norm_int(last_m.get("qty")), 1)
                    last_m["unit_price"] = _ceil_int(last_m["total"] / qty)
                else:
                    v.setdefault("works", []).append({
                        "name": "Дополнительные работы сегмента",
                        "unit": "компл", "qty": 1,
                        "unit_price": diff, "total": diff,
                    })

                total_works = sum(_norm_int(w.get("total")) for w in (v.get("works") or []))
                total_materials = sum(_norm_int(m.get("total")) for m in (v.get("materials") or []))
                total = total_works + total_materials

        v["total_works"] = total_works
        v["total_materials"] = total_materials
        v["total"] = total
        v["budget"] = f"{total:,} ₽".replace(",", " ")
        prev_total = total
    return variants


# ---------------------------------------------------------------------------
# Главная нормализация результата
# ---------------------------------------------------------------------------
def _normalize_result(data: dict, project: dict | None = None) -> dict:
    out = {
        "summary": data.get("summary") or data.get("description") or "",
        "cost_min": 0, "cost_max": 0,
        "currency": data.get("currency") or "₽",
        "risks": data.get("risks") or data.get("notes") or "",
        "variants": [],
    }

    # Извлекаем площадь пола из проекта, если передан
    project_area: float | None = None
    if project:
        try:
            project_area = float(project.get("area_m2") or 0) or None
        except (TypeError, ValueError):
            project_area = None

    for v in (data.get("variants") or data.get("options") or [])[:3]:
        works = []
        for w in (v.get("works") or []):
            qty = _norm_int(w.get("qty") or 0)
            unit_price = _norm_int(w.get("unit_price") or 0)
            total = _norm_int(w.get("total") or 0)
            if total <= 0 and qty > 0 and unit_price > 0:
                total = qty * unit_price
            works.append({"name": w.get("name") or "", "unit": w.get("unit") or "",
                           "qty": qty, "unit_price": unit_price, "total": total})

        works = _fix_ceiling_plaster_prices(works)

        materials = []
        for m in (v.get("materials") or []):
            qty = _norm_int(m.get("qty") or 0)
            unit_price = _norm_int(m.get("unit_price") or 0)
            total = _norm_int(m.get("total") or 0)
            if total <= 0 and qty > 0 and unit_price > 0:
                total = qty * unit_price
            materials.append({"name": m.get("name") or "", "brand": m.get("brand") or "",
                               "unit": m.get("unit") or "", "qty": qty,
                               "unit_price": unit_price, "total": total})

        # 1+5. Арифметическая валидация всех строк
        works = _fix_line_arithmetic(works)
        materials = _fix_line_arithmetic(materials)
        # 2. Исправить цены импортных материалов
        materials = _fix_import_prices(materials)
        # 3. Пересчитать штукатурку по норме расхода
        materials = _fix_consumable_materials(works, materials)
        # 4. Добавить грунтовку если есть штукатурка
        works, materials = _ensure_primer_before_plaster(works, materials, out["currency"])
        # 5. Синхронизация площадей напольных покрытий
        works, materials = _fix_floor_area_sync(works, materials, project_area)
        # 6. Исправить пропорцию работы/материалы
        works = _fix_works_ratio(works, materials)

        total_works = sum(w["total"] for w in works)
        total_materials = sum(m["total"] for m in materials)
        total = total_works + total_materials

        variant = {
            "name": v.get("name") or "",
            "style": v.get("style") or "",
            "total_works": total_works, "total_materials": total_materials, "total": total,
            "budget": v.get("budget") or f"{total:,} ₽".replace(",", " "),
            "works": works, "materials": materials,
            "pros": v.get("pros") or "", "cons": v.get("cons") or "",
        }
        # 7. Потолок цены эконом-напольного покрытия
        variant = _fix_econom_floor_cap(variant)
        # 8. Убрать фразы самокритики
        variant = _fix_self_doubt_phrases(variant)
        out["variants"].append(_ensure_nonempty_variant_fields(variant))

    # 9. Проверить полноту Премиума
    out["variants"] = _fix_variant_completeness(out["variants"])
    # 10. Принудительный разрыв 25% между уровнями
    out["variants"] = _enforce_variant_order(out["variants"])

    totals = [v["total"] for v in out["variants"] if v["total"] > 0]
    if totals:
        out["cost_min"] = min(totals)
        out["cost_max"] = max(totals)
    else:
        out["cost_min"] = _norm_int(data.get("cost_min") or data.get("min_cost") or 0)
        out["cost_max"] = _norm_int(data.get("cost_max") or data.get("max_cost") or 0)

    return out


def _estimate_looks_incomplete(result: dict, scope_info: dict) -> bool:
    scope = scope_info.get("scope")
    variants = result.get("variants") or []
    if not variants:
        return True

    first = variants[0]
    works_count = len(first.get("works") or [])
    mats_count = len(first.get("materials") or [])

    if any(v.get("_incomplete") for v in variants):
        return True

    if scope == "full_apartment":
        return works_count < 8 or mats_count < 5 or first.get("total", 0) < 250000
    if scope == "bathroom":
        return works_count < 5 or mats_count < 4
    if scope == "floor_only":
        return works_count < 3 or mats_count < 2
    return False


def _parse_retry_after(exc: RateLimitError) -> float:
    try:
        return float(exc.response.json()["error"]["metadata"]["retry_after_seconds"])
    except Exception:
        return 15.0


async def _try_model(
    client: AsyncOpenAI,
    model: str,
    messages: list,
    max_tokens: int,
    use_json_mode: bool,
    project: dict | None = None,
) -> dict:
    kwargs: dict = dict(model=model, messages=messages, temperature=0.3, max_tokens=max_tokens)
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = await client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content
    parsed = json.loads(_clean_json(raw))
    return _normalize_result(parsed, project=project)


async def get_estimate(situation: str, project: dict | None = None, user_id: int | None = None) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model_chain = await _get_model_chain(api_key)
    if not model_chain:
        raise RuntimeError("Нет доступных моделей")

    scope_info = _detect_scope(situation)
    materials_context_full = await get_materials_context(situation, limit=12)
    materials_context_groq = await get_materials_context(situation, limit=3)
    user_rates = get_user_rates(user_id) if user_id else []
    rates_context = _build_rates_context(user_rates)

    user_msg_full = _build_user_message(situation, project, materials_context_full, rates_context, scope_info)
    user_msg_groq = _build_user_message(situation, project, materials_context_groq, rates_context, scope_info)

    for model, base_url in model_chain:
        local = _is_local(base_url)
        groq = _is_groq(base_url)

        if local:
            system_prompt = SYSTEM_PROMPT_LOCAL
            max_tokens = 2200
        elif groq:
            system_prompt = SYSTEM_PROMPT_GROQ
            max_tokens = 1800
        else:
            system_prompt = SYSTEM_PROMPT
            max_tokens = 5200

        use_json_mode = local or groq
        user_msg = user_msg_groq if groq else user_msg_full
        client = _make_client(base_url, api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        json_attempts = 0
        provider_tag = "local" if local else ("groq" if groq else "openrouter")

        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            try:
                result = await _try_model(client, model, messages, max_tokens, use_json_mode, project=project)
                if _estimate_looks_incomplete(result, scope_info):
                    logger.warning(
                        "Estimate incomplete for scope=%s via %s, retrying",
                        scope_info.get("scope"), model
                    )
                    for v in result.get("variants", []):
                        v.pop("_incomplete", None)
                    messages.append({
                        "role": "user",
                        "content": (
                            "Предыдущая смета неполная. Исправь: "
                            "1) Арифметика: qty×unit_price=total в каждой строке; пересчитай total_works и total как суммы строк. "
                            "2) Премиум должен содержать столько же этапов работ, что и Эконом/Оптимальный (не менее 80% позиций материалов). "
                            "3) Пропорция работы/материалы: работы >= 30% от итога. "
                            "4) Импортные материалы (Польша/Германия/Италия) — цена не ниже рынка. "
                            "5) Разрыв цен: Оптимальный на 20-30% дороже Эконома, Премиум на 25-50% дороже Оптимального. "
                            "6) Все разделы обязательных этапов присутствуют в каждом варианте. "
                            "7) Эконом: напольное покрытие не дороже 1900₽/м². "
                            "8) Несколько типов пола: сумма их площадей = площадь пола; для каждого — строка укладки. "
                            "9) Никаких фраз 'требует уточнения' — замени допущениями или убери секцию."
                        ),
                    })
                    result = await _try_model(client, model, messages, max_tokens, use_json_mode, project=project)
                logger.info("Estimate OK via %s (%s)", model, provider_tag)
                return result
            except NotFoundError:
                logger.warning("Model not found: %s", model)
                _free_models_cache.clear()
                break
            except RateLimitError as exc:
                wait = _parse_retry_after(exc)
                if wait <= MAX_RATE_LIMIT_WAIT and attempt < len(RETRY_DELAYS):
                    logger.warning("Rate limited on %s, waiting %.0fs", model, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.warning("Rate limit too long (%.0fs) on %s, skipping", wait, model)
                    break
            except APIStatusError as exc:
                if exc.status_code == 413:
                    logger.warning("Payload too large (413) for %s (%s), skipping", model, provider_tag)
                    break
                raise
            except (APITimeoutError, APIConnectionError):
                if attempt < len(RETRY_DELAYS):
                    logger.warning("Timeout on %s, retrying in %ds", model, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.warning("All retries failed for %s", model)
                    break
            except json.JSONDecodeError:
                json_attempts += 1
                if json_attempts < JSON_MAX_RETRIES:
                    logger.warning("Bad JSON from %s (attempt %d), retrying", model, json_attempts)
                    await asyncio.sleep(2)
                else:
                    logger.warning("Bad JSON from %s, skipping", model)
                    break

    raise RuntimeError("Ни одна модель не ответила")
