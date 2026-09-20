from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db.models import Site, Task


def kb_foreman_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏗 Мои объекты"), KeyboardButton(text="➕ Новый объект")],
            [KeyboardButton(text="📋 Задачи"), KeyboardButton(text="💬 Чат")],
        ],
        resize_keyboard=True,
    )


def kb_sites_inline(sites: list[Site], action: str = "site") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🏗 {s.name}", callback_data=f"{action}:{s.id}")]
        for s in sites
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_site_actions(site_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Задачи", callback_data=f"f_tasks:{site_id}")],
        [InlineKeyboardButton(text="➕ Создать задачу", callback_data=f"f_newtask:{site_id}")],
        [InlineKeyboardButton(text="👷 Добавить рабочего", callback_data=f"f_addworker:{site_id}")],
        [InlineKeyboardButton(text="🔗 Инвайт-ссылка", callback_data=f"f_invite:{site_id}")],
        [InlineKeyboardButton(text="💬 Чат объекта", callback_data=f"f_chat:{site_id}")],
    ])


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
