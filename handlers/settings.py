from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from db.models import User
from locales.i18n import t

router = Router()


def kb_settings(lang: str, notifications: bool) -> InlineKeyboardMarkup:
    lang_label = "🇷🇺 RU → EN" if lang == "ru" else ("🇬🇧 EN → RU" if lang == "en" else "🌐 Язык / Language")
    notif_key = "settings_notif_on" if notifications else "settings_notif_off"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang_label, callback_data="stg_lang")],
        [InlineKeyboardButton(text=t(notif_key, lang), callback_data="stg_notif")],
    ])


SETTINGS_TEXTS = {
    "ru": ["⚙️ Настройки"],
    "en": ["⚙️ Settings"],
    "tg": ["⚙️ Танзимот"],
    "uz": ["⚙️ Sozlamalar"],
}
ALL_SETTINGS_LABELS = [label for labels in SETTINGS_TEXTS.values() for label in labels]


@router.message(F.text.in_(ALL_SETTINGS_LABELS))
async def settings_handler(message: Message, user: User):
    await message.answer(
        t("settings_title", user.lang),
        reply_markup=kb_settings(user.lang, user.notifications),
    )


@router.callback_query(F.data == "stg_lang")
async def toggle_lang(call: CallbackQuery, user: User, session: AsyncSession):
    langs = ["ru", "en", "tg", "uz"]
    current_idx = langs.index(user.lang) if user.lang in langs else 0
    new_lang = langs[(current_idx + 1) % len(langs)]
    await session.execute(update(User).where(User.id == user.id).values(lang=new_lang))
    await session.commit()
    user.lang = new_lang
    await call.message.edit_reply_markup(reply_markup=kb_settings(new_lang, user.notifications))
    await call.answer()


@router.callback_query(F.data == "stg_notif")
async def toggle_notif(call: CallbackQuery, user: User, session: AsyncSession):
    new_val = not user.notifications
    await session.execute(update(User).where(User.id == user.id).values(notifications=new_val))
    await session.commit()
    user.notifications = new_val
    await call.message.edit_reply_markup(reply_markup=kb_settings(user.lang, new_val))
    await call.answer()
