#!/bin/bash
# Запуск прораб-бота на macOS
# Помести в /usr/local/bin/start_bot.sh или прямо в папке проекта

cd "$(dirname "$0")"

# Загрузить .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Используем python из виртуального окружения если есть
if [ -d venv ]; then
  source venv/bin/activate
fi

exec python bot.py
