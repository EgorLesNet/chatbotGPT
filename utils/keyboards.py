from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Смета", callback_data="nav:estimate"),
            InlineKeyboardButton(text="📂 Проекты", callback_data="nav:projects"),
        ],
        [
            InlineKeyboardButton(text="💸 Расценки", callback_data="nav:rates"),
            InlineKeyboardButton(text="💳 Подписка", callback_data="nav:subscribe"),
        ],
        [
            InlineKeyboardButton(text="📊 Мой статус", callback_data="nav:status"),
        ],
    ])


def rates_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="rates:add"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="rates:edit"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data="rates:delete"),
        ],
        [
            InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu"),
        ],
    ])


def back_kb(label: str = "Главное меню") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"◀️ {label}", callback_data="nav:menu")],
    ])


def after_estimate_kb(has_projects: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📂 Добавить в проект" if has_projects else "📂 Создать проект",
                callback_data="estimate:add_to_project",
            )
        ],
        [
            InlineKeyboardButton(text="📄 PDF для заказчика", callback_data="estimate:pdf"),
        ],
        [
            InlineKeyboardButton(text="◀️ Главное меню", callback_data="nav:menu"),
        ],
    ])
