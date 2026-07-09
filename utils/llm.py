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
    {
      "name": "Эконом",
      "budget": "50 000 – 60 000 ₽",
      "style": "Простой и практичный",
      "materials": [{"name": "Название", "price": "цена/ед.", "note": "пояснение"}],
      "pros": "Плюсы", "cons": "Минусы"
    },
    {
      "name": "Оптимальный",
      "budget": "65 000 – 75 000 ₽",
      "style": "Современный минимализм",
      "materials": [{"name": "Название", "price": "цена/ед.", "note": "пояснение"}],
      "pros": "Плюсы", "cons": "Минусы"
    },
    {
      "name": "Премиум",
      "budget": "75 000 – 90 000 ₽",
      "style": "Дизайнерский",
      "materials": [{"name": "Название", "price": "цена/ед.", "note": "пояснение"}],
      "pros": "Плюсы", "cons": "Минусы"
    }
  ],
  "risks": "Что важно учесть прорабу"
}
Правила:
- Цены реалистичные для России, учитывай площадь
- Возвращай ONLY raw JSON, no markdown fences
"""

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
HTTPX_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=5.0)
RETRY_DELAYS = [2, 5, 15]
MAX_RATE_LIMIT_WAIT = 30  # ждём до 30с на rate limit
JSON_MAX_RETRIES = 2      # повторных попыток при плохом JSON

_BLOCKLIST_KEYWORDS = [
    "content-safety", "moderation", "guard", "embedding",
    "rerank", "classify", "whisper", "tts",
]

_free_models_cache: list[str] = []


def _is_chat_model(model_id: str) -> bool:
    mid = model_id.lower()
    return not any(kw in mid for kw in _BLOCKLIST_KEYWORDS)


async def _get_ollama_models() -> list[str]:
    """Returns list of locally available Ollama models, or empty list."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                logger.info("Ollama models available: %s", models)
                return [f"ollama/{m}" for m in models]
    except Exception:
        pass
    return []


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
        logger.info("Loaded %d free chat models: %s", len(_free_models_cache), _free_models_cache)
        return _free_models_cache
    except Exception:
        logger.warning("Could not fetch OpenRouter models", exc_info=True)
        return []


def _make_client(base_url: str, api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key or "ollama",
        base_url=base_url,
        timeout=HTTPX_TIMEOUT,
        max_retries=0,
        default_headers={
            "HTTP-Referer": os.getenv("APP_URL", "https://github.com/EgorLesNet/chatbotGPT"),
            "X-Title": "ProrabBot",
        } if "openrouter" in base_url else {},
    )


async def _get_model_chain(api_key: str) -> list[tuple[str, str]]:
    """
    Returns list of (model_id, base_url) tuples.
    Ollama local models go first if available.
    """
    chain: list[tuple[str, str]] = []

    # 1. Локальные Ollama-модели
    ollama_models = await _get_ollama_models()
    for m in ollama_models:
        model_name = m.removeprefix("ollama/")
        chain.append((model_name, OLLAMA_BASE_URL))

    # 2. Указанная в .env модель
    primary = os.getenv("OPENROUTER_MODEL", "").strip()
    if primary:
        chain.append((primary, OPENROUTER_BASE_URL))

    # 3. Автоподбор из OpenRouter API
    free_models = await fetch_free_models(api_key)
    for m in free_models:
        if not any(m == c[0] for c in chain):
            chain.append((m, OPENROUTER_BASE_URL))

    return chain


def _build_user_message(situation: str, project: dict | None, materials_context: str) -> str:
    parts = [f"Ситуация клиента: {situation}"]
    if project:
        parts.append(f"Объект: {project.get('title', '')}")
        parts.append(f"Тип: {project.get('project_type', '')}")
        parts.append(f"Площадь: {project.get('area_m2', '')} м²")
        if project.get("notes"):
            parts.append(f"Доп. заметки: {project['notes']}")
    if materials_context:
        parts.append(f"\n{materials_context}")
    return "\n".join(parts)


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    # Ищем первый { если модель добавила текст до JSON
    brace = raw.find("{")
    if brace > 0:
        raw = raw[brace:]
    return raw.strip()


def _parse_retry_after(exc: RateLimitError) -> float:
    try:
        body = exc.response.json()
        return float(body["error"]["metadata"]["retry_after_seconds"])
    except Exception:
        return 15.0


async def _try_model(client: AsyncOpenAI, model: str, messages: list) -> dict:
    response = await client.chat.completions.create(
        model=model, messages=messages, temperature=0.4, max_tokens=1800,
    )
    raw = response.choices[0].message.content
    return json.loads(_clean_json(raw))


async def get_estimate(situation: str, project: dict | None = None) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model_chain = await _get_model_chain(api_key)

    materials_context = await get_materials_context(situation, limit=3)
    user_msg = _build_user_message(situation, project, materials_context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    for model, base_url in model_chain:
        client = _make_client(base_url, api_key)
        json_attempts = 0

        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            try:
                result = await _try_model(client, model, messages)
                logger.info("Estimate OK via %s @ %s", model, base_url)
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
                    logger.warning("Bad JSON from %s after %d attempts, skipping", model, json_attempts)
                    break

    raise RuntimeError("Ни одна модель не ответила")
