const MAP: Record<string, string> = {
  forbidden: "Недостаточно прав для этого действия.",
  "not found": "Не найдено.",
  "wrong status": "Статус задачи уже изменился. Обновите страницу.",
  "name required": "Введите название (минимум 2 символа).",
  "title required": "Введите название задачи (минимум 2 символа).",
  "profile required": "Сначала настройте профиль.",
  "not authenticated": "Сессия истекла. Войдите заново.",
};

export function explain(message: string): string {
  return MAP[message] ?? message;
}
