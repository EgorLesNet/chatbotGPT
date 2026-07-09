# Прораб-Бот

Телеграм-бот для прораба: описываешь ситуацию клиента — получаешь смету и три варианта материалов от нейросети.

## Ключевая функция

`/estimate` — прораб описывает что хочет клиент (стиль, бюджет, цвет, тип работ), нейросеть возвращает:
- Краткое описание работ
- Примерную стоимость (мин–макс)
- **3 варианта материалов**: Эконом / Оптимальный / Премиум
- Риски и нюансы для прораба

Free-план показывает 1 вариант, paid-план — все 3.

## Структура

```
chatbotGPT/
├── bot.py
├── Dockerfile
├── fly.toml
├── handlers/
│   ├── estimate.py   # /estimate — ситуация → смета + материалы
│   ├── project.py    # /project, /newproject — FSM
│   ├── start.py
│   ├── rates.py
│   ├── materials.py
│   ├── subscribe.py
│   └── voice.py
├── utils/
│   ├── llm.py         # OpenRouter API
│   ├── storage.py
│   ├── subscription.py
│   └── pdf.py
├── db/
│   ├── users/         # персистентный диск fly.io
│   └── materials.json
├── .env.example
├── requirements.txt
└── README.md
```

## Тарифы

| | Free | Paid |
|---|---|---|
| Проектов в месяц | 1 | безлимит |
| Вариантов материалов | 1 | 3 |

## Деплой на fly.io

```bash
# 1. Установи flyctl
curl -L https://fly.io/install.sh | sh

# 2. Авторизация
fly auth login

# 3. Создай приложение (из папки проекта)
fly launch --no-deploy

# 4. Создай персистентный диск
fly volumes create prorab_db --region ams --size 1

# 5. Добавь секреты
fly secrets set BOT_TOKEN=your_token
fly secrets set OPENROUTER_API_KEY=sk-or-v1-...

# 6. Деплой
fly deploy
```

## Полезные команды fly

```bash
fly logs          # смотреть логи в реальном времени
fly status        # статус машины
fly deploy        # обновить бот
fly secrets list  # список секретов
```

## Команды бота

- `/start` — стартовое меню
- `/estimate` — главная фича: ситуация → смета + материалы
- `/project` / `/newproject` — управление проектами
- `/rates` — ориентиры по расценкам
- `/materials` — подбор из базы
- `/subscribe` — статус подписки
