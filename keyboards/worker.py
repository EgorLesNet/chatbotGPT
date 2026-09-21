from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db.models import Site, Task
from locales.i18n import t


def kb_worker_main(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_worker_sites", lang)), KeyboardButton(text=t("btn_worker_tasks", lang))],
            [KeyboardButton(text=t("btn_worker_chat", lang))],
        ],
        resize_keyboard=True,
    )


def kb_sites_inline(sites: list[Site], action: str = "w_site") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🏗 {s.name}", callback_data=f"{action}:{s.id}")]
        for s in sites
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_task_worker(task_id: int, status: str, lang: str = "ru") -> InlineKeyboardMarkup:
    buttons = []
    if status == "open":
        buttons.append([InlineKeyboardButton(text=t("btn_take_task", lang), callback_data=f"w_take:{task_id}")])
    elif status == "in_progress":
        buttons.append([InlineKeyboardButton(text=t("btn_done_task", lang), callback_data=f"w_done:{task_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_tasks_inline(tasks: list[Task], prefix: str = "w_task") -> InlineKeyboardMarkup:
    status_emoji = {"open": "🔵", "in_progress": "🟡", "done": "🟢"}
    buttons = [
        [InlineKeyboardButton(
            text=f"{status_emoji.get(task.status.value, '⚪')} {task.title}",
            callback_data=f"{prefix}:{task.id}"
        )]
        for task in tasks
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
