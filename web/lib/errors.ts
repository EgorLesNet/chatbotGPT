const MAP: Record<string, string> = {
  forbidden: "Недостаточно прав для этого действия.",
  "not found": "Не найдено.",
  "wrong status": "Статус задачи уже изменился. Обновите страницу.",
  "name required": "Введите название (минимум 2 символа).",
  "title required": "Введите название задачи (минимум 2 символа).",
  "profile required": "Сначала настройте профиль.",
  "not authenticated": "Сессия истекла. Войдите заново.",
  "worker not in site": "Этот рабочий не добавлен на объект.",
  "comment required": "Напишите комментарий к отчёту.",
  "photo required": "Добавьте хотя бы одно фото.",
  "too many photos": "Не более 10 фото.",
  "bad photo path": "Фото не принадлежит этой задаче. Повторите загрузку.",
  "photo not found": "Фото не загрузилось. Повторите попытку.",
};

export function explain(message: string): string {
  if (message.includes("value too long")) return "Слишком длинный текст. Сократите название или адрес.";
  return MAP[message] ?? message;
}
