from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db.models import Site, Task


def kb_worker_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏗 Мои объекты"), KeyboardButton(text="📋 Мои задачи")],
            [KeyboardButton(text="💬 Чат рабочего")],
        ],
        resize_keyboard=True,
    )


def kb_sites_inline(sites: list[Site], action: str = "w_site") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🏗 {s.name}", callback_data=f"{action}:{s.id}")]
        for s in sites
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_task_worker(task_id: int, status: str) -> InlineKeyboardMarkup:
    buttons = []
    if status == "open":
        buttons.append([InlineKeyboardButton(text="▶️ Взять задачу", callback_data=f"w_take:{task_id}")])
    elif status == "in_progress":
        buttons.append([InlineKeyboardButton(text="✅ Отметить выполненной", callback_data=f"w_done:{task_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_tasks_inline(tasks: list[Task], prefix: str = "w_task") -> InlineKeyboardMarkup:
    status_emoji = {"open": "🔵", "in_progress": "🟡", "done": "🟢"}
    buttons = [
        [InlineKeyboardButton(
            text=f"{status_emoji.get(t.status.value, '⚪')} {t.title}",
            callback_data=f"{prefix}:{t.id}"
        )]
        for t in tasks
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
