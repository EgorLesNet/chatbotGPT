import os
import json
import logging
from openai import AsyncOpenAI
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


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": os.getenv("APP_URL", "https://github.com/EgorLesNet/chatbotGPT"),
            "X-Title": "ProrabBot",
        },
    )


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


async def get_estimate(situation: str, project: dict | None = None) -> dict:
    client = _get_client()
    model = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")

    # Шаг 1: база → фоллбек в интернет
    materials_context = await get_materials_context(situation, limit=3)

    # Шаг 2: LLM с контекстом
    user_msg = _build_user_message(situation, project, materials_context)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.4,
        max_tokens=1800,
    )
    raw = response.choices[0].message.content
    return json.loads(_clean_json(raw))
