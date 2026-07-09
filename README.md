# 🤖 TG AI Bot

Telegram-бот с ИИ на базе бесплатных моделей [OpenRouter](https://openrouter.ai).

## Возможности
- 🆓 20 бесплатных сообщений в день на пользователя
- 💎 Безлимит для подписчиков Tribute-канала
- 🔄 Автосброс счётчика каждую ночь
- 🧠 Контекст диалога (последние 10 сообщений)
- ⚡ Fallback по нескольким бесплатным моделям

## Команды
| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и инструкция |
| `/reset` | Очистить историю диалога |
| `/status` | Сколько сообщений осталось |

## Установка на macOS 10.13+

### 1. Клонировать репозиторий
```bash
git clone https://github.com/EgorLesNet/chatbotGPT.git
cd chatbotGPT
```

### 2. Создать виртуальное окружение
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Установить зависимости
```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения
```bash
cp .env.example .env
nano .env  # заполни BOT_TOKEN и OPENROUTER_API_KEY
```

### 5. Запустить бота
```bash
python3 main.py
```

### 6. Автозапуск через launchd (macOS)
Создай файл `~/Library/LaunchAgents/com.tgaibot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tgaibot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/chatbotGPT/venv/bin/python3</string>
        <string>/path/to/chatbotGPT/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/chatbotGPT</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>BOT_TOKEN</key>
        <string>your_token</string>
        <key>OPENROUTER_API_KEY</key>
        <string>your_key</string>
        <key>TRIBUTE_CHANNEL</key>
        <string>@yourchannel</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/tgaibot.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/tgaibot.err</string>
</dict>
</plist>
```
Затем:
```bash
launchctl load ~/Library/LaunchAgents/com.tgaibot.plist
```

## Как работает Tribute-проверка

1. В [@BotFather](https://t.me/BotFather) выдай боту права администратора в Tribute-канале (или он должен быть участником).
2. Укажи `TRIBUTE_CHANNEL=@твой_канал` в `.env`.
3. Бот проверит через `getChatMember` — если пользователь в канале, лимит снимается.

## Получить ключи
- **BOT_TOKEN** — [@BotFather](https://t.me/BotFather)
- **OPENROUTER_API_KEY** — [openrouter.ai/keys](https://openrouter.ai/keys) (бесплатно)
