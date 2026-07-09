import os


def build_project_prompt(project: dict, user_request: str) -> str:
    return (
        "Ты помощник для прораба. "
        "Отвечай кратко, по делу и с упором на смету, объёмы работ и материалы.\n\n"
        f"Проект: {project.get('title', 'без названия')}\n"
        f"Тип: {project.get('project_type', 'не указан')}\n"
        f"Площадь: {project.get('area_m2', 'не указана')} м²\n"
        f"Комментарий: {project.get('notes', '—')}\n\n"
        f"Запрос пользователя: {user_request}"
    )


def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "stub")


def get_llm_reply(project: dict, user_request: str) -> dict:
    prompt = build_project_prompt(project, user_request)
    return {
        "provider": get_llm_provider(),
        "prompt": prompt,
        "answer": "Черновая заготовка ответа LLM: оценить объёмы, подобрать 2-3 сценария работ и вынести риски в отдельный блок.",
    }
