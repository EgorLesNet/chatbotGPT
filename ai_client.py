import os
from openai import AsyncOpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Список бесплатных моделей OpenRouter, идём по очереди при ошибке/лимите
FREE_MODELS = [
    "deepseek/deepseek-chat-v3-0324:free",
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
]

SYSTEM_PROMPT = {
    "role": "system",
    "content": "Ты дружелюбный ассистент в Telegram-боте. Отвечай кратко и по делу на русском языке.",
}


async def ask_ai(history: list[dict]) -> tuple[str, str]:
    messages = [SYSTEM_PROMPT] + history

    last_error = None
    for model in FREE_MODELS:
        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_headers={
                    "HTTP-Referer": "https://github.com/your-repo",
                    "X-Title": "TG AI Bot",
                },
                max_tokens=800,
            )
            answer = completion.choices[0].message.content
            if answer:
                return answer.strip(), model
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Все модели недоступны: {last_error}")


def reset_history():
    pass
