from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from locales.i18n import LANGUAGES


def kb_lang() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"set_lang:{code}")]
        for code, label in LANGUAGES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
