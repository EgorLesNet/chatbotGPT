#!/bin/bash
# Установка на macOS 10.13 без Homebrew
# Запускай: bash setup_macos_old.sh

set -e
cd "$(dirname "$0")"

echo "==> Проверяем Python..."
PY=""
for candidate in python3.11 python3.10 python3.9 python3; do
  if command -v "$candidate" &>/dev/null; then
    VER=$("$candidate" -c 'import sys; print(sys.version_info[:2])')
    echo "    Нашёл: $candidate ($VER)"
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  echo ""
  echo "Python не найден."
  echo "Скачай и установи Python 3.9 вручную:"
  echo "  https://www.python.org/ftp/python/3.9.18/python-3.9.18-macosx10.9.pkg"
  echo "После установки запусти этот скрипт ещё раз."
  open "https://www.python.org/ftp/python/3.9.18/python-3.9.18-macosx10.9.pkg" 2>/dev/null || true
  exit 1
fi

echo "==> Создаём виртуальное окружение..."
"$PY" -m venv venv
source venv/bin/activate

echo "==> Устанавливаем зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Создаём .env если нет..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    Открой .env и впиши BOT_TOKEN и OPENROUTER_API_KEY"
fi

mkdir -p logs db/users

echo ""
echo "✅ Готово! Дальше:"
echo "  1. nano .env       — впиши BOT_TOKEN и OPENROUTER_API_KEY"
echo "  2. bash start_bot.sh  — запустить бота"
