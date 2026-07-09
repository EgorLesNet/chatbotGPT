import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


async def search_material_prices(situation: str) -> str:
    """
    Ищет актуальные цены на стройматериалы через Tavily Search API.
    Возвращает строку с результатами для вставки в промпт LLM.
    Если ключ не задан или запрос упал — возвращает пустую строку.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return ""

    query = f"цены на стройматериалы ремонт {situation[:120]} 2025 2026 Россия"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 4,
        "include_answer": True,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(TAVILY_URL, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    logger.warning("Tavily returned %s", resp.status)
                    return ""
                data = await resp.json()

        parts = []
        if data.get("answer"):
            parts.append(f"Краткий ответ из поиска: {data['answer']}")
        for r in data.get("results", [])[:3]:
            snippet = r.get("content", "")[:300]
            parts.append(f"- {r.get('title', '')}: {snippet}")

        return "\n".join(parts) if parts else ""
    except Exception:
        logger.warning("Tavily search failed", exc_info=True)
        return ""
