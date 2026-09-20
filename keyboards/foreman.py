from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db.models import Site, Task


def kb_foreman_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏗 Мои объекты"), KeyboardButton(text="➕ Создать объект")],
            [KeyboardButton(text="📋 Задачи"), KeyboardButton(text="➕ Создать задачу")],
            [KeyboardButton(text="👷 Рабочие"), KeyboardButton(text="💬 Чат")],
        ],
        resize_keyboard=True,
    )


def kb_sites_inline(sites: list[Site], action: str = "f_site") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🏗 {s.name}", callback_data=f"{action}:{s.id}")]
        for s in sites
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_tasks_inline(tasks: list[Task], prefix: str = "f_task") -> InlineKeyboardMarkup:
    status_emoji = {"open": "🔵", "in_progress": "🟡", "done": "🟢"}
    buttons = [
        [InlineKeyboardButton(
            text=f"{status_emoji.get(t.status.value, '⚪')} {t.title}",
            callback_data=f"{prefix}:{t.id}"
        )]
        for t in tasks
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_task_foreman(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить задачу", callback_data=f"f_deltask:{task_id}")],
    ])
