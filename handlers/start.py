from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from utils.storage import ensure_user, get_user_projects, get_user_summary, reset_user_month
from utils.subscription import get_plan_limits, get_plan_name, is_paid_active
from utils.keyboards import main_menu_kb

router = Router()


def _menu_text(user: dict) -> str:
    plan = get_plan_name(user)
    limits = get_plan_limits(user)
    paid = is_paid_active(user)
    plan_icon = "💳" if paid else "🆓"
    return (
        "🤖 <b>Prorab AI</b>\n"
        "────────────────────\n"
        "Бот помогает составить предварительную смету ремонта за минуту.\n"
        "Упрощает работу прорабам.\n"
        "────────────────────\n"
        f"{plan_icon} План: <b>{plan}</b>\n"
        f"📁 Проектов/месяц: <b>{limits['projects_per_month_label']}</b>\n"
        "────────────────────\n"
        "📋 <b>Смета</b> — опиши задачу, бот рассчитает 3 варианта\n"
        "📂 <b>Проекты</b> — карточки объектов с историей смет\n"
        "💸 <b>Расценки</b> — твои ставки на работы (бот их учитывает)\n"
        "💳 <b>Подписка</b> — free / paid-план"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    await message.answer(_menu_text(user), reply_markup=main_menu_kb())


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    await message.answer(_menu_text(user), reply_markup=main_menu_kb())


@router.callback_query(F.data == "nav:menu")
async def cb_nav_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = ensure_user(call.from_user)
    await call.message.answer(_menu_text(user), reply_markup=main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "nav:status")
async def cb_nav_status(call: CallbackQuery) -> None:
    from utils.keyboards import back_kb
    user = ensure_user(call.from_user)
    reset_user_month(user["id"])
    projects = get_user_projects(user["id"])
    summary = get_user_summary(user["id"])
    plan = get_plan_name(user)
    paid_text = "активна" if is_paid_active(user) else "не активна"
    await call.message.answer(
        "📊 <b>Статус аккаунта</b>\n\n"
        f"План: <b>{plan}</b>\n"
        f"Подписка: <b>{paid_text}</b>\n"
        f"Оплачено до: <b>{user.get('paid_until') or '—'}</b>\n"
        f"Проектов в этом месяце: <b>{summary['projects_created_this_month']}</b>\n"
        f"Всего проектов: <b>{len(projects)}</b>",
        reply_markup=back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "nav:subscribe")
async def cb_nav_subscribe(call: CallbackQuery) -> None:
    from utils.keyboards import back_kb
    from utils.subscription import is_paid_active, get_plan_name
    user = ensure_user(call.from_user)
    active = is_paid_active(user)
    plan = get_plan_name(user)
    plan_icon = "💳" if active else "🆓"
    await call.message.answer(
        f"💳 <b>Подписка</b>\n\n"
        f"{plan_icon} Текущий план: <b>{plan}</b>\n"
        f"Статус: <b>{'активна' if active else 'не активна'}</b>\n"
        f"Оплачено до: <b>{user.get('paid_until') or '—'}</b>\n\n"
        "🆓 <b>Free</b> — 1 проект в месяц, только вариант «Эконом» целиком\n"
        "💳 <b>Paid</b> — безлимит проектов, все 3 варианта с детализацией, выгрузка PDF",
        reply_markup=back_kb(),
    )
    await call.answer()


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    from utils.keyboards import back_kb
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    projects = get_user_projects(user["id"])
    summary = get_user_summary(user["id"])
    plan = get_plan_name(user)
    paid_text = "активна" if is_paid_active(user) else "не активна"
    await message.answer(
        "📊 <b>Статус аккаунта</b>\n\n"
        f"План: <b>{plan}</b>\n"
        f"Подписка: <b>{paid_text}</b>\n"
        f"Оплачено до: <b>{user.get('paid_until') or '—'}</b>\n"
        f"Проектов в этом месяце: <b>{summary['projects_created_this_month']}</b>\n"
        f"Всего проектов: <b>{len(projects)}</b>",
        reply_markup=back_kb(),
    )
