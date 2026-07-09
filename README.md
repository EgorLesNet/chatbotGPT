# 🤖 TG AI Bot с подпиской через Tribute

Telegram-бот с ИИ на базе бесплатных моделей [OpenRouter](https://openrouter.ai).
Подписочная модель реализована через [Tribute](https://tribute.tg) webhook API.

## Как это работает

```
Пользователь покупает продукт в Tribute
        ↓
Tribute отправляет POST /tribute на твой сервер
        ↓
Бот получает telegram_id покупателя
        ↓
В базе ставится subscribed=True + дата истечения
        ↓
Пользователь получает уведомление и безлимитный доступ
```

## Возможности
- 🆓 20 бесплатных сообщений в день
- 💎 Безлимит для подписчиков Tribute
- 🔄 Автосброс счётчика каждую ночь
- 🧠 Контекст диалога (последние 10 сообщений)
- ⚡ Fallback по нескольким бесплатным моделям

## Команды
| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/reset` | Очистить историю диалога |
| `/status` | Статус подписки и лимит |

## Установка на macOS 10.13+

> ⚠️ Нужен Python 3.10+. Установи через `brew install python@3.10`

```bash
git clone https://github.com/EgorLesNet/chatbotGPT.git
cd chatbotGPT
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # заполни все переменные
python3 main.py
```

## Настройка Tribute Webhook

1. Зайди в [@tribute](https://t.me/tribute) → **Дэшборд автора** → **Настройки (⋮)** → **API-ключи**
2. Сгенерируй API-ключ → скопируй в `TRIBUTE_API_KEY`
3. В поле **Webhook URL** укажи: `https://твой_домен/tribute`
4. Tribute будет слать POST-запросы на этот URL при каждой покупке/продлении/отмене

### Как пробросить порт для локального запуска (macOS)
Используй [ngrok](https://ngrok.com) для теста:
```bash
brew install ngrok
ngrok http 8080
# Скопируй https://xxxx.ngrok.io → укажи как https://xxxx.ngrok.io/tribute в Tribute
```

## Поддерживаемые события Tribute
| Событие | Действие |
|---------|----------|
| `newSubscription` | Активировать подписку на 30 дней |
| `renewedSubscription` | Продлить подписку на 30 дней |
| `cancelledSubscription` | Деактивировать подписку |

## Переменные окружения
См. [`.env.example`](.env.example)

## Автозапуск через launchd (macOS)
Создай `~/Library/LaunchAgents/com.tgaibot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.tgaibot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/chatbotGPT/venv/bin/python3</string>
        <string>/path/to/chatbotGPT/main.py</string>
    </array>
    <key>WorkingDirectory</key><string>/path/to/chatbotGPT</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>BOT_TOKEN</key><string>TOKEN</string>
        <key>OPENROUTER_API_KEY</key><string>KEY</string>
        <key>TRIBUTE_API_KEY</key><string>KEY</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/tgaibot.log</string>
    <key>StandardErrorPath</key><string>/tmp/tgaibot.err</string>
</dict>
</plist>
```
```bash
launchctl load ~/Library/LaunchAgents/com.tgaibot.plist
```

## Получить ключи
- **BOT_TOKEN** → [@BotFather](https://t.me/BotFather)
- **OPENROUTER_API_KEY** → [openrouter.ai/keys](https://openrouter.ai/keys)
- **TRIBUTE_API_KEY** → [@tribute](https://t.me/tribute) → Дэшборд → Настройки → API-ключи
