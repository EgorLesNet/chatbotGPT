import os
import json
import logging
import asyncio
import re
import httpx
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, NotFoundError, RateLimitError
from utils.materials_db import get_materials_context
from utils.storage import get_user_rates

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — опытный прораб в России. Составь подробную смету ремонта в трёх вариантах: Эконом, Оптимальный, Премиум.

КРИТИЧЕСКИ ВАЖНО:
- Вариант Эконом должен быть полностью пригоден для показа клиенту: с полным перечнем работ, материалов и точных цен.
- Варианты Оптимальный и Премиум тоже считай полностью, НО они нужны как платные апсейл-варианты.
- Для всех вариантов стоимость работ должна рассчитываться на основе пользовательских расценок мастера, если они переданы во входных данных. Если расценка есть, не придумывай свою цену за работу, а используй её.
- Если точной расценки на конкретную работу нет, используй ближайший по смыслу ориентир или реалистичную рыночную цену.
- Материалы подбирай из предоставленного списка материалов. Если список неполный, можно дополнять реалистичными рыночными материалами.
- Варианты должны отличаться и по материалам, и по итоговой стоимости.

Верни JSON строго такого вида:
{
  "summary": "Краткое описание работ и сроков",
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
      "works": [
        {"name": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}
      ],
      "materials": [
        {"name": "", "brand": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}
      ],
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
      "works": [
        {"name": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}
      ],
      "materials": [
        {"name": "", "brand": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}
      ],
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
      "works": [
        {"name": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}
      ],
      "materials": [
        {"name": "", "brand": "", "unit": "", "qty": 0, "unit_price": 0, "total": 0}
      ],
      "pros": "",
      "cons": ""
    }
  ],
  "risks": ""
}
ONLY raw JSON, no markdown.
""".strip()

SYSTEM_PROMPT_LOCAL = (
    "Отвечай ONLY чистым JSON. Смета ремонта в РФ в 3 вариантах. "
    "Используй расценки мастера на работы, если они переданы. "
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


def _build_rates_context(user_rates: list[dict]) -> str:
    if not user_rates:
        return ""
    lines = ["Расценки мастера по работам (используй их в первую очередь):"]
    for item in user_rates:
        lines.append(
            f"- {item.get('name','')}: {item.get('unit_price',0)} ₽/{item.get('unit','')} ({item.get('note','')})"
        )
    return "\n".join(lines)


def _build_user_message(situation: str, project: dict | None, materials_context: str, rates_context: str) -> str:
    parts = [f"Ситуация: {situation}"]
    if project:
        parts.append(f"Объект: {project.get('title', '')}, тип: {project.get('project_type', '')}, {project.get('area_m2', '')} м²")
        if project.get("notes"):
            parts.append(f"Заметки: {project['notes']}")
    if rates_context:
        parts.append(rates_context)
    if materials_context:
        parts.append(materials_context)
    return "\n".join(parts)


def _clean_json(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = raw.replace("```", "")
    raw = raw.strip()
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


def _normalize_result(data: dict) -> dict:
    out = {
        "summary": data.get("summary") or data.get("description") or "",
        "cost_min": _norm_int(data.get("cost_min") or data.get("min_cost") or 0),
        "cost_max": _norm_int(data.get("cost_max") or data.get("max_cost") or 0),
        "currency": data.get("currency") or "₽",
        "risks": data.get("risks") or data.get("notes") or "",
        "variants": [],
    }
    for v in (data.get("variants") or data.get("options") or [])[:3]:
        works = []
        for w in (v.get("works") or []):
            works.append({
                "name": w.get("name") or "",
                "unit": w.get("unit") or "",
                "qty": _norm_int(w.get("qty") or 0),
                "unit_price": _norm_int(w.get("unit_price") or 0),
                "total": _norm_int(w.get("total") or 0),
            })
        materials = []
        for m in (v.get("materials") or []):
            materials.append({
                "name": m.get("name") or "",
                "brand": m.get("brand") or "",
                "unit": m.get("unit") or "",
                "qty": _norm_int(m.get("qty") or 0),
                "unit_price": _norm_int(m.get("unit_price") or 0),
                "total": _norm_int(m.get("total") or 0),
            })
        total_works = _norm_int(v.get("total_works") or sum(w["total"] for w in works))
        total_materials = _norm_int(v.get("total_materials") or sum(m["total"] for m in materials))
        total = _norm_int(v.get("total") or total_works + total_materials)
        out["variants"].append({
            "name": v.get("name") or "",
            "style": v.get("style") or "",
            "total_works": total_works,
            "total_materials": total_materials,
            "total": total,
            "budget": v.get("budget") or f"{total:,} ₽".replace(",", " "),
            "works": works,
            "materials": materials,
            "pros": v.get("pros") or "",
            "cons": v.get("cons") or "",
        })
    return out


def _parse_retry_after(exc: RateLimitError) -> float:
    try:
        return float(exc.response.json()["error"]["metadata"]["retry_after_seconds"])
    except Exception:
        return 15.0


async def _try_model(client: AsyncOpenAI, model: str, messages: list, max_tokens: int, use_json_mode: bool) -> dict:
    kwargs: dict = dict(model=model, messages=messages, temperature=0.3, max_tokens=max_tokens)
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = await client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content
    parsed = json.loads(_clean_json(raw))
    return _normalize_result(parsed)


async def get_estimate(situation: str, project: dict | None = None, user_id: int | None = None) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model_chain = await _get_model_chain(api_key)
    if not model_chain:
        raise RuntimeError("Нет доступных моделей")

    materials_context = await get_materials_context(situation, limit=5)
    user_rates = get_user_rates(user_id) if user_id else []
    rates_context = _build_rates_context(user_rates)
    user_msg = _build_user_message(situation, project, materials_context, rates_context)

    for model, base_url in model_chain:
        local = _is_local(base_url)
        groq = _is_groq(base_url)
        system_prompt = SYSTEM_PROMPT_LOCAL if local else SYSTEM_PROMPT
        max_tokens = 1400 if local else 3200
        use_json_mode = local or groq
        client = _make_client(base_url, api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        json_attempts = 0
        provider_tag = "local" if local else ("groq" if groq else "openrouter")

        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            try:
                result = await _try_model(client, model, messages, max_tokens, use_json_mode)
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
