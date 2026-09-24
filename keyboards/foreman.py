from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db.models import Site, Task
from locales.i18n import t

BACK_BTN = {"ru": "⬅️ Назад", "en": "⬅️ Back", "tg": "⬅️ Бозгашт", "uz": "⬅️ Orqaga"}


def kb_back(lang: str = "ru", cb: str = "back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BACK_BTN.get(lang, "⬅️ Назад"), callback_data=cb)]
    ])


def kb_foreman_main(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_my_sites", lang)), KeyboardButton(text=t("btn_create_site", lang))],
            [KeyboardButton(text=t("btn_tasks", lang)), KeyboardButton(text=t("btn_create_task", lang))],
            [KeyboardButton(text=t("btn_workers", lang)), KeyboardButton(text=t("btn_chat", lang))],
            [KeyboardButton(text=t("btn_settings", lang))],
        ],
        resize_keyboard=True,
    )


def kb_sites_inline(sites: list[Site], action: str = "f_site", lang: str = "ru") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🏗 {s.name}", callback_data=f"{action}:{s.id}")]
        for s in sites
    ]
    buttons.append([InlineKeyboardButton(text=BACK_BTN.get(lang, "⬅️ Назад"), callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_tasks_inline(tasks: list[Task], prefix: str = "f_task", lang: str = "ru") -> InlineKeyboardMarkup:
    status_emoji = {"open": "🔵", "in_progress": "🟡", "review": "🟠", "done": "🟢"}
    buttons = [
        [InlineKeyboardButton(
            text=f"{status_emoji.get(task.status.value, '⚪')} {task.title}",
            callback_data=f"{prefix}:{task.id}"
        )]
        for task in tasks
    ]
    buttons.append([InlineKeyboardButton(text=BACK_BTN.get(lang, "⬅️ Назад"), callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_task_foreman(task_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_delete_task", lang), callback_data=f"f_deltask:{task_id}")],
        [InlineKeyboardButton(text=BACK_BTN.get(lang, "⬅️ Назад"), callback_data="back")],
    ])


def kb_review_actions(task_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_rework", lang), callback_data=f"f_rework:{task_id}")],
        [InlineKeyboardButton(text=t("btn_accept_review", lang), callback_data=f"f_accept:{task_id}")],
        [InlineKeyboardButton(text=BACK_BTN.get(lang, "⬅️ Назад"), callback_data="back")],
    ])
