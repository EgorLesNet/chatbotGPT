from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import get_sites_for_worker
from keyboards.worker import kb_worker_main, kb_sites_inline

router = Router()


@router.message(F.text == "🏗 Мои объекты")
async def worker_my_sites(message: Message, session: AsyncSession, current_user):
    if not current_user or current_user.role != UserRole.worker:
        return
    sites = await get_sites_for_worker(session, current_user.id)
    if not sites:
        await message.answer(
            "Вы не состоите ни в одном объекте.\n"
            "Попросите прораба отправить вам инвайт-ссылку.",
            reply_markup=kb_worker_main(),
        )
        return
    await message.answer("Ваши объекты:", reply_markup=kb_sites_inline(sites))
