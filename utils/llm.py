import os
import json
import logging
import asyncio
import re
import httpx
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, NotFoundError, RateLimitError
from utils.materials_db import get_materials_context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — опытный помощник прораба. Твоя задача — по описанию ситуации клиента дать чёткую профессиональную оценку.
Если предоставлены данные о материалах — используй их для точных цен в смете.

Формат ответа СТРОГО в JSON (no markdown blocks):
{
  "summary": "Краткое описание работ (2-3 предложения)",
  "cost_min": 50000,
  "cost_max": 80000,
  "currency": "₽",
  "variants": [
    {"name": "Эконом", "budget": "50 000 – 60 000 ₽", "style": "Простой",
     "materials": [{"name": "", "price": "", "note": ""}], "pros": "", "cons": ""},
    {"name": "Оптимальный", "budget": "65 000 – 75 000 ₽", "style": "Современный",
     "materials": [{"name": "", "price": "", "note": ""}], "pros": "", "cons": ""},
    {"name": "Премиум", "budget": "75 000 – 90 000 ₽", "style": "Дизайнерский",
     "materials": [{"name": "", "price": "", "note": ""}], "pros": "", "cons": ""}
  ],
  "risks": "Что важно учесть прорабу"
}
Правила: цены реалистичные для России. ONLY raw JSON, no text before or after.
""".strip()

SYSTEM_PROMPT_LOCAL = """
Прораб Россия. Оцени ремонт. Отвечай строго в JSON без лишнего текста:
{"summary":"","cost_min":0,"cost_max":0,"currency":"₽","variants":[{"name":"Эконом","budget":"","style":"","materials":[{"name":"","price":"","note":""}],"pros":"","cons":""},{"name":"Оптимальный","budget":"","style":"","materials":[{"name":"","price":"","note":""}],"pros":"","cons":""},{"name":"Премиум","budget":"","style":"","materials":[{"name":"","price":"","note":""}],"pros":"","cons":""}],"risks":""}
Цены в рублях, актуальные для России. ONLY raw JSON.
""".strip()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLAMACPP_DEFAULT_URL = "http://localhost:11434"

HTTPX_TIMEOUT_LOCAL = httpx.Timeout(connect=5.0, read=600.0, write=15.0, pool=5.0)
HTTPX_TIMEOUT_CLOUD = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=5.0)

RETRY_DELAYS = [3, 10]
MAX_RATE_LIMIT_WAIT = 30
JSON_MAX_RETRIES = 2

_BLOCKLIST_KEYWORDS = [
    "content-safety", "moderation", "guard", "embedding",
    "rerank", "classify", "whisper", "tts",
]
_free_models_cache: list[str] = []


def _is_chat_model(model_id: str) -> bool:
    return not any(kw in model_id.lower() for kw in _BLOCKLIST_KEYWORDS)


def _is_local(base_url: str) -> bool:
    return "localhost" in base_url or "127.0.0.1" in base_url


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


async def fetch_free_models(api_key: str) -> list[str]:
    """Fetch free OpenRouter models. Returns [] on any network error."""
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
    return AsyncOpenAI(
        api_key="local" if local else api_key,
        base_url=base_url,
        timeout=HTTPX_TIMEOUT_LOCAL if local else HTTPX_TIMEOUT_CLOUD,
        max_retries=0,
        default_headers={} if local else {
            "HTTP-Referer": os.getenv("APP_URL", "https://github.com/EgorLesNet/chatbotGPT"),
            "X-Title": "ProrabBot",
        },
    )


async def _get_model_chain(api_key: str) -> list[tuple[str, str]]:
    """
    Сначала проверяем локальную модель (не зависит от интернета),
    затем добавляем облачные если интернет доступен.
    """
    chain: list[tuple[str, str]] = []

    # 1. Локальная модель — не нужен интернет
    local = await _check_llamacpp()
    if local:
        chain.append(local)

    # 2. Облачные — только если есть сеть
    primary = os.getenv("OPENROUTER_MODEL", "").strip()
    if primary:
        chain.append((primary, OPENROUTER_BASE_URL))

    free_models = await fetch_free_models(api_key)  # [] если сеть недоступна
    for m in free_models:
        if not any(m == c[0] for c in chain):
            chain.append((m, OPENROUTER_BASE_URL))

    if not chain:
        logger.error("No models available (no local server, no internet)")

    return chain


def _build_user_message(situation: str, project: dict | None, materials_context: str) -> str:
    parts = [f"Ситуация: {situation}"]
    if project:
        parts.append(f"Объект: {project.get('title', '')}, тип: {project.get('project_type', '')}, {project.get('area_m2', '')} м²")
        if project.get("notes"):
            parts.append(f"Заметки: {project['notes']}")
    if materials_context:
        parts.append(materials_context)
    return "\n".join(parts)


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    brace = raw.find("{")
    if brace > 0:
        raw = raw[brace:]
    return raw.strip()


def _parse_retry_after(exc: RateLimitError) -> float:
    try:
        return float(exc.response.json()["error"]["metadata"]["retry_after_seconds"])
    except Exception:
        return 15.0


async def _try_model(client: AsyncOpenAI, model: str, messages: list, max_tokens: int) -> dict:
    response = await client.chat.completions.create(
        model=model, messages=messages, temperature=0.4, max_tokens=max_tokens,
    )
    raw = response.choices[0].message.content
    return json.loads(_clean_json(raw))


async def get_estimate(situation: str, project: dict | None = None) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model_chain = await _get_model_chain(api_key)

    if not model_chain:
        raise RuntimeError("Нет доступных моделей")

    materials_context = await get_materials_context(situation, limit=3)
    user_msg = _build_user_message(situation, project, materials_context)

    for model, base_url in model_chain:
        local = _is_local(base_url)
        system_prompt = SYSTEM_PROMPT_LOCAL if local else SYSTEM_PROMPT
        max_tokens = 800 if local else 1800
        client = _make_client(base_url, api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        json_attempts = 0

        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            try:
                result = await _try_model(client, model, messages, max_tokens)
                logger.info("Estimate OK via %s (%s)", model, "local" if local else "cloud")
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
