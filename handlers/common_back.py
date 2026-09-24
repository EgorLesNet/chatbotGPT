"""Global handler for the 'back' callback — clears state and returns user to main menu."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from db.models import UserRole
from keyboards.foreman import kb_foreman_main
from keyboards.worker import kb_worker_main
from locales.i18n import t

router = Router()


@router.callback_query(F.data == "back")
async def back_handler(call: CallbackQuery, state: FSMContext, current_user, lang: str):
    await state.clear()
    if current_user and current_user.role == UserRole.foreman:
        kb = kb_foreman_main(lang)
        text = t("welcome_back", lang, name=current_user.name)
    elif current_user and current_user.role == UserRole.worker:
        kb = kb_worker_main(lang)
        text = t("welcome_back", lang, name=current_user.name)
    else:
        await call.answer()
        return
    await call.message.answer(text, reply_markup=kb)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()
