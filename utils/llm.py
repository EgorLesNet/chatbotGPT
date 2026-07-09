import os
import json
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — опытный помощник прораба. Твоя задача — по описанию ситуации клиента дать чёткую профессиональную оценку.

Формат ответа СТРОГО в JSON:
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
        {"name": "Название материала", "price": "цена за ед.", "note": "краткое пояснение"}
      ],
      "pros": "Плюсы варианта",
      "cons": "Минусы варианта"
    },
    {
      "name": "Оптимальный",
      "budget": "65 000 – 75 000 ₽",
      "style": "Современный минимализм",
      "materials": [
        {"name": "Название материала", "price": "цена за ед.", "note": "краткое пояснение"}
      ],
      "pros": "Плюсы варианта",
      "cons": "Минусы варианта"
    },
    {
      "name": "Премиум",
      "budget": "75 000 – 90 000 ₽",
      "style": "Дизайнерский",
      "materials": [
        {"name": "Название материала", "price": "цена за ед.", "note": "краткое пояснение"}
      ],
      "pros": "Плюсы варианта",
      "cons": "Минусы варианта"
    }
  ],
  "risks": "Что важно учесть прорабу"
}

Правила:
- Учитывай площадь объекта если указана
- Цены реалистичные, актуальные для России, 2024-2026
- Материалы подбирай исходя из стиля, бюджета и ситуации клиента
- Возвращай ТОЛЬКО JSON без markdown-блоков
"""


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _build_user_message(situation: str, project: dict | None) -> str:
    parts = [f"Ситуация клиента: {situation}"]
    if project:
        parts.append(f"Объект: {project.get('title', '')}")
        parts.append(f"Тип: {project.get('project_type', '')}")
        parts.append(f"Площадь: {project.get('area_m2', '')} м²")
        if project.get('notes'):
            parts.append(f"Доп. заметки: {project['notes']}")
    return "\n".join(parts)


async def get_estimate(situation: str, project: dict | None = None) -> dict:
    """Returns parsed estimate dict from LLM, or raises on failure."""
    client = _get_client()
    user_msg = _build_user_message(situation, project)
    response = await client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.4,
        max_tokens=1800,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    return json.loads(raw)
