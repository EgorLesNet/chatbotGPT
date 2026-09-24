from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import get_user_by_phone, create_user
from keyboards.common import kb_phone, kb_role, kb_remove
from keyboards.foreman import kb_foreman_main
from keyboards.worker import kb_worker_main
from keyboards.lang import kb_lang
from locales.i18n import t, LANGUAGES

router = Router()


class RegState(StatesGroup):
    lang = State()
    phone = State()
    name = State()
    role = State()


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext, current_user, lang: str):
    await state.clear()
    if current_user:
        if current_user.role == UserRole.foreman:
            await message.answer(t("welcome_back", lang, name=current_user.name), reply_markup=kb_foreman_main(lang))
        else:
            await message.answer(t("welcome_back", lang, name=current_user.name), reply_markup=kb_worker_main(lang))
        return
    await state.set_state(RegState.lang)
    await message.answer(t("choose_language", "ru"), reply_markup=kb_lang())


@router.callback_query(F.data.startswith("set_lang:"), RegState.lang)
async def pick_lang(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    lang = callback.data.split(":")[1]
    if lang not in LANGUAGES:
        await callback.answer()
        return
    await state.update_data(lang=lang)
    await callback.message.edit_text(t("welcome", lang))
    await callback.message.answer(t("share_phone_btn", lang), reply_markup=kb_phone(lang))
    await state.set_state(RegState.phone)
    await callback.answer()


@router.message(RegState.phone, F.contact)
async def reg_phone(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    phone = message.contact.phone_number.lstrip("+")
    existing = await get_user_by_phone(session, phone)
    if existing:
        await message.answer(t("phone_already_registered", lang), reply_markup=kb_remove())
        await state.clear()
        return
    await state.update_data(phone=phone)
    await message.answer(t("enter_name", lang), reply_markup=kb_remove())
    await state.set_state(RegState.name)


@router.message(RegState.name)
async def reg_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(name=message.text.strip())
    await message.answer(t("choose_role", lang), reply_markup=kb_role(lang))
    await state.set_state(RegState.role)


@router.message(RegState.role)
async def reg_role(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    text = message.text.strip()
    role_map = {
        t("role_foreman", l): UserRole.foreman for l in ("ru", "en", "tg", "uz")
    }
    role_map.update({
        t("role_worker", l): UserRole.worker for l in ("ru", "en", "tg", "uz")
    })
    role = role_map.get(text)
    if not role:
        await message.answer(t("choose_role", lang), reply_markup=kb_role(lang))
        return
    user = await create_user(session, message.from_user.id, data["phone"], data["name"], role, lang)
    await state.clear()
    if role == UserRole.foreman:
        await message.answer(t("reg_done", lang, name=user.name), reply_markup=kb_foreman_main(lang))
    else:
        await message.answer(t("reg_done", lang, name=user.name), reply_markup=kb_worker_main(lang))
