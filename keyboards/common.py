from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def kb_remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def kb_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_role() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👷 Я прораб")],
            [KeyboardButton(text="🔨 Я рабочий")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
