import os
import json
import logging
import asyncio
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
HTTPX_TIMEOUT = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=5.0)
RETRY_DELAYS = [2, 5, 10]
MAX_RATE_LIMIT_WAIT = 20  # ждём не больше N секунд на rate limit, иначе переходим к следующей модели

_free_models_cache: list[str] = []


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
            if m["id"].endswith(":free")
            or str(m.get("pricing", {}).get("prompt", "1")) == "0"
        ]
        priority = ["llama", "gemma", "qwen", "nemotron", "hermes"]
        free.sort(key=lambda mid: next((i for i, kw in enumerate(priority) if kw in mid), len(priority)))
        _free_models_cache = free[:8]
        logger.info("Loaded %d free models: %s", len(_free_models_cache), _free_models_cache)
        return _free_models_cache
    except Exception:
        logger.warning("Could not fetch models list", exc_info=True)
        return ["openrouter/auto"]


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE_URL,
        timeout=HTTPX_TIMEOUT,
        max_retries=0,
        default_headers={
            "HTTP-Referer": os.getenv("APP_URL", "https://github.com/EgorLesNet/chatbotGPT"),
            "X-Title": "ProrabBot",
        },
    )


async def _get_model_chain(api_key: str) -> list[str]:
    primary = os.getenv("OPENROUTER_MODEL", "").strip()
    free_models = await fetch_free_models(api_key)
    if primary and primary not in free_models:
        return [primary] + free_models
    if primary:
        return [primary] + [m for m in free_models if m != primary]
    return free_models


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
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _parse_retry_after(exc: RateLimitError) -> float:
    """Extract retry_after_seconds from OpenRouter 429 response."""
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
    client = _get_client()
    model_chain = await _get_model_chain(api_key)

    materials_context = await get_materials_context(situation, limit=3)
    user_msg = _build_user_message(situation, project, materials_context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    last_exc: Exception | None = None

    for model in model_chain:
        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            try:
                result = await _try_model(client, model, messages)
                if model != model_chain[0]:
                    logger.info("Succeeded with model: %s", model)
                return result

            except NotFoundError:
                logger.warning("Model not found: %s — skipping", model)
                _free_models_cache.clear()
                break

            except RateLimitError as exc:
                wait = _parse_retry_after(exc)
                if wait <= MAX_RATE_LIMIT_WAIT and attempt < len(RETRY_DELAYS):
                    logger.warning("Rate limited on %s, waiting %.0fs...", model, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.warning("Rate limit too long (%.0fs) on %s — trying next model", wait, model)
                    last_exc = exc
                    break

            except (APITimeoutError, APIConnectionError) as exc:
                last_exc = exc
                if attempt < len(RETRY_DELAYS):
                    logger.warning("Timeout on %s (attempt %d), retrying in %ds", model, attempt, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.warning("All retries failed for %s", model)
                    break

            except json.JSONDecodeError as exc:
                logger.warning("Bad JSON from %s", model)
                last_exc = exc
                break

    if isinstance(last_exc, (APITimeoutError, APIConnectionError)):
        raise TimeoutError("Все модели недоступны")
    if isinstance(last_exc, json.JSONDecodeError):
        raise ValueError("Некорректный ответ")
    raise RuntimeError("Ни одна модель не ответила")
