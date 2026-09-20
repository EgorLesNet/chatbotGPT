from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, Contact
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserRole
from db.repo import (
    get_user_by_telegram_id, create_user,
    get_site_by_invite_code, is_member, add_member, get_user_by_phone
)
from keyboards.common import kb_phone, kb_role, kb_remove
from keyboards.foreman import kb_foreman_main
from keyboards.worker import kb_worker_main

router = Router()


class RegState(StatesGroup):
    waiting_phone = State()
    waiting_role = State()
    waiting_name = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, current_user, bot: Bot):
    args = message.text.split(maxsplit=1)[1] if message.text and len(message.text.split()) > 1 else ""
    invite_code = args.strip() if args else ""

    if current_user:
        # Уже зарегистрирован — обработать инвайт если есть
        if invite_code:
            await _handle_invite(message, session, current_user, invite_code, bot)
        else:
            await _show_main(message, current_user)
        return

    await state.update_data(invite_code=invite_code)
    await message.answer(
        "👋 Добро пожаловать на платформу <b>Прораб</b>!\n\nПоделитесь номером телефона для регистрации:",
        reply_markup=kb_phone(),
    )
    await state.set_state(RegState.waiting_phone)


@router.message(RegState.waiting_phone, F.contact)
async def reg_phone(message: Message, state: FSMContext, session: AsyncSession):
    contact: Contact = message.contact
    phone = contact.phone_number.replace("+", "").strip()
    existing = await get_user_by_phone(session, phone)
    if existing:
        await message.answer("⚠️ Этот номер уже зарегистрирован.", reply_markup=kb_remove())
        await state.clear()
        return
    await state.update_data(phone=phone)
    await message.answer("Как вас зовут? (имя и фамилия)", reply_markup=kb_remove())
    await state.set_state(RegState.waiting_name)


@router.message(RegState.waiting_name)
async def reg_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите имя:")
        return
    await state.update_data(name=name)
    await message.answer("Выберите вашу роль:", reply_markup=kb_role())
    await state.set_state(RegState.waiting_role)


@router.message(RegState.waiting_role, F.text.in_(["👷 Я прораб", "🔨 Я рабочий"]))
async def reg_role(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    role = UserRole.foreman if "прораб" in message.text else UserRole.worker
    data = await state.get_data()
    user = await create_user(
        session,
        telegram_id=message.from_user.id,
        phone=data["phone"],
        name=data["name"],
        role=role,
    )
    await state.clear()

    invite_code = data.get("invite_code", "")
    if invite_code:
        await _handle_invite(message, session, user, invite_code, bot)
    else:
        await message.answer(
            f"✅ Регистрация завершена! Добро пожаловать, <b>{user.name}</b>!",
            reply_markup=kb_foreman_main() if role == UserRole.foreman else kb_worker_main(),
        )


async def _handle_invite(message: Message, session, user, invite_code: str, bot: Bot):
    site = await get_site_by_invite_code(session, invite_code)
    if not site:
        await message.answer("❌ Неверный инвайт-код.", reply_markup=kb_worker_main())
        return
    if await is_member(session, site.id, user.id):
        await message.answer(
            f"ℹ️ Вы уже участник объекта <b>{site.name}</b>.",
            reply_markup=kb_worker_main(),
        )
        return
    await add_member(session, site.id, user.id)
    # Уведомить прораба
    foreman_result = await session.get(type(user).__class__, site.foreman_id) if False else None
    from db.repo import get_user_by_telegram_id as _g
    from db.models import User
    from sqlalchemy import select
    res = await session.execute(select(User).where(User.id == site.foreman_id))
    foreman = res.scalar_one_or_none()
    if foreman:
        try:
            await bot.send_message(
                foreman.telegram_id,
                f"👷 <b>{user.name}</b> присоединился к объекту <b>{site.name}</b> по инвайт-ссылке."
            )
        except Exception:
            pass
    await message.answer(
        f"✅ Вы успешно присоединились к объекту <b>{site.name}</b>!",
        reply_markup=kb_worker_main(),
    )


async def _show_main(message: Message, user):
    from keyboards.foreman import kb_foreman_main
    from keyboards.worker import kb_worker_main
    from db.models import UserRole
    kb = kb_foreman_main() if user.role == UserRole.foreman else kb_worker_main()
    await message.answer(f"👋 С возвращением, <b>{user.name}</b>!", reply_markup=kb)
