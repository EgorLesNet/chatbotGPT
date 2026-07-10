from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from utils.storage import ensure_user, get_user_projects, get_user_summary, reset_user_month
from utils.subscription import get_plan_limits, get_plan_name, is_paid_active

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    limits = get_plan_limits(user)
    await message.answer(
        "👷 <b>Прораб-Бот</b> — помощник по проектам, расценкам и сметам.\n\n"
        f"Текущий план: <b>{get_plan_name(user)}</b>\n"
        f"Проектов в месяц: <b>{limits['projects_per_month_label']}</b>\n"
        f"Вариантов материалов на запрос: <b>{limits['material_options']}</b>\n\n"
        "Команды:\n"
        "/estimate — описать ситуацию клиента → смета\n"
        "/project — создать или посмотреть проект\n"
        "/rates — мои расценки на работы\n"
        "/rates_add — добавить расценку\n"
        "/rates_edit — изменить расценку\n"
        "/rates_delete — удалить расценку\n"
        "/subscribe — статус подписки\n"
        "/voice — голосовой режим (заготовка)"
    )


@router.message(Command("status"))
@router.message(Command("menu"))
async def cmd_status(message: Message) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    projects = get_user_projects(user["id"])
    summary = get_user_summary(user["id"])
    plan = get_plan_name(user)
    paid_text = "активна" if is_paid_active(user) else "не активна"
    await message.answer(
        "📊 <b>Статус пользователя</b>\n\n"
        f"План: <b>{plan}</b>\n"
        f"Подписка: <b>{paid_text}</b>\n"
        f"Оплачено до: <b>{user.get('paid_until') or '—'}</b>\n"
        f"Проектов в этом месяце: <b>{summary['projects_created_this_month']}</b>\n"
        f"Всего проектов: <b>{len(projects)}</b>"
    )
