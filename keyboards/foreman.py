from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db.models import Site, Task
from locales.i18n import t


def kb_foreman_main(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_my_sites", lang)), KeyboardButton(text=t("btn_create_site", lang))],
            [KeyboardButton(text=t("btn_tasks", lang)), KeyboardButton(text=t("btn_create_task", lang))],
            [KeyboardButton(text=t("btn_workers", lang)), KeyboardButton(text=t("btn_chat", lang))],
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


def kb_task_foreman(task_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_delete_task", lang), callback_data=f"f_deltask:{task_id}")],
    ])
