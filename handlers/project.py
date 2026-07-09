from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.storage import create_project, ensure_user, get_user_projects, reset_user_month
from utils.subscription import can_create_project, get_plan_limits

router = Router()


@router.message(Command("project"))
async def cmd_project(message: Message) -> None:
    user = ensure_user(message.from_user)
    reset_user_month(user["id"])
    existing = get_user_projects(user["id"])

    if not existing:
        if not can_create_project(user):
            limits = get_plan_limits(user)
            await message.answer(
                "🚫 Лимит по free-плану исчерпан.\n"
                f"Можно создать только <b>{limits['projects_per_month_label']}</b>.\n"
                "Оформи paid-план для безлимита."
            )
            return

        project = create_project(
            user_id=user["id"],
            title="Новый объект",
            project_type="квартира",
            area_m2=42,
            notes="Черновая отделка, стартовый шаблон",
        )
        await message.answer(
            "🏗 <b>Создан стартовый проект</b>\n\n"
            f"ID: <b>{project['id']}</b>\n"
            f"Название: <b>{project['title']}</b>\n"
            f"Тип: <b>{project['project_type']}</b>\n"
            f"Площадь: <b>{project['area_m2']} м²</b>\n\n"
            "Дальше можно расширить сценарий до пошагового опроса."
        )
        return

    lines = ["📁 <b>Проекты пользователя</b>"]
    for project in existing[-10:]:
        lines.append(
            f"• <b>{project['title']}</b> — {project['project_type']}, {project['area_m2']} м², создан {project['created_at'][:10]}"
        )
    await message.answer("\n".join(lines))
