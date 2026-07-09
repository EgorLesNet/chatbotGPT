import os
import json
import logging
import asyncio
import httpx
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, NotFoundError
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
      "materials": [
        {"name": "Название", "price": "цена/ед.", "note": "пояснение"}
      ],
      "pros": "Плюсы",
      "cons": "Минусы"
    },
    {
      "name": "Оптимальный",
      "budget": "65 000 – 75 000 ₽",
      "style": "Современный минимализм",
      "materials": [
        {"name": "Название", "price": "цена/ед.", "note": "пояснение"}
      ],
      "pros": "Плюсы",
      "cons": "Минусы"
    },
    {
      "name": "Премиум",
      "budget": "75 000 – 90 000 ₽",
      "style": "Дизайнерский",
      "materials": [
        {"name": "Название", "price": "цена/ед.", "note": "пояснение"}
      ],
      "pros": "Плюсы",
      "cons": "Минусы"
    }
  ],
  "risks": "Что важно учесть прорабу"
}

Правила:
- Учитывай площадь объекта если указана
- Цены реалистичные, актуальные для России 2024-2026
- Материалы подбирай исходя из стиля, бюджета и ситуации клиента
- Возвращай ONLY raw JSON, no markdown fences
"""

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Цепочка fallback-моделей: пробуем по порядку если предыдущая недоступна
FALLBACK_MODELS = [
    "deepseek/deepseek-r1:free",
    "google/gemma-3-12b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "microsoft/phi-4-reasoning:free",
]

HTTPX_TIMEOUT = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=5.0)
RETRY_DELAYS = [2, 5, 10]


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


def _get_model_chain() -> list[str]:
    """Primary model from .env + fallbacks (without duplicates)."""
    primary = os.getenv("OPENROUTER_MODEL", FALLBACK_MODELS[0])
    chain = [primary] + [m for m in FALLBACK_MODELS if m != primary]
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
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


async def _try_model(client: AsyncOpenAI, model: str, messages: list) -> dict:
    """Single attempt with one model. Raises on any error."""
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
        max_tokens=1800,
    )
    raw = response.choices[0].message.content
    return json.loads(_clean_json(raw))


async def get_estimate(situation: str, project: dict | None = None) -> dict:
    client = _get_client()
    model_chain = _get_model_chain()

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
                    logger.info("Succeeded with fallback model: %s", model)
                return result

            except NotFoundError:
                logger.warning("Model not available on OpenRouter: %s — skipping", model)
                last_exc = None
                break  # эта модель недоступна, переходим к следующей

            except (APITimeoutError, APIConnectionError) as exc:
                last_exc = exc
                if attempt < len(RETRY_DELAYS):
                    logger.warning(
                        "Timeout on %s (attempt %d/%d), retrying in %ds...",
                        model, attempt, len(RETRY_DELAYS), delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning("All retries failed for model %s, trying next", model)
                    break

            except json.JSONDecodeError as exc:
                logger.warning("Bad JSON from %s: %s", model, exc)
                last_exc = exc
                break  # плохой ответ модели, пробуем следующую

    if isinstance(last_exc, (APITimeoutError, APIConnectionError)):
        raise TimeoutError("Все модели недоступны")
    if isinstance(last_exc, json.JSONDecodeError):
        raise ValueError("Некорректный ответ")
    raise RuntimeError("Ни одна модель не ответила")
